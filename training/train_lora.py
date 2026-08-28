"""Дообучение LoRA-адаптера на наборе диалогов (этап 2 программы).

Скрипт намеренно использует базовые API ``transformers.Trainer`` + ``peft``
без обёрток: так проще понимать, что происходит, и объяснять на защите.

Ключевая деталь — **функция потерь считается только на ответе ассистента**:
токены системного промпта и контекста маскируются (-100). Иначе модель учится
воспроизводить документацию, а не отвечать по ней.

Запуск::

    pip install -e ".[train]" bitsandbytes
    python training/train_lora.py --config training/lora_config.yaml
    python training/train_lora.py --config training/lora_config.yaml --dry-run   # только проверка данных

Тяжёлые зависимости импортируются лениво, поэтому ``--dry-run`` работает
на любой машине без GPU и без установленного PyTorch.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

import yaml

from techdoc_assistant.prompts import is_refusal


def load_config(path: str | Path) -> dict:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required = {"base_model", "dataset", "output_dir", "lora"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"В конфигурации не хватает ключей: {sorted(missing)}")
    return config


def load_examples(path: str | Path) -> list[dict]:
    examples = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        example = json.loads(line)
        messages = example.get("messages")
        if not messages or messages[-1].get("role") != "assistant":
            raise ValueError(f"{path}:{line_no}: ожидается список messages, заканчивающийся ответом assistant")
        examples.append(example)
    return examples


def describe(examples: list[dict]) -> None:
    lengths = [sum(len(m["content"]) for m in ex["messages"]) for ex in examples]
    answers = [len(ex["messages"][-1]["content"]) for ex in examples]
    refusals = sum(1 for ex in examples if is_refusal(ex["messages"][-1]["content"]))
    print(f"Примеров: {len(examples)}")
    print(f"Средняя длина диалога: {sum(lengths) / max(len(lengths), 1):.0f} символов, максимум {max(lengths, default=0)}")
    print(f"Средняя длина ответа: {sum(answers) / max(len(answers), 1):.0f} символов")
    print(f"Примеров с отказом: {refusals}")


def train(config: dict, examples: list[dict]) -> None:  # pragma: no cover - требует GPU
    import torch
    import transformers
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
    )

    tokenizer = AutoTokenizer.from_pretrained(config["base_model"])
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    use_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    compute_dtype = torch.bfloat16 if use_bf16 else torch.float16
    major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
    dtype_key = "dtype" if (major, minor) >= (4, 56) else "torch_dtype"  # переименовано в новых версиях

    quant = config.get("quantization", {}) or {}
    model_kwargs: dict = {dtype_key: compute_dtype, "device_map": "auto"}
    if quant.get("load_in_4bit"):
        from transformers import BitsAndBytesConfig

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(config["base_model"], **model_kwargs)
    if quant.get("load_in_4bit"):
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora = config["lora"]
    model = get_peft_model(
        model,
        LoraConfig(
            r=int(lora.get("r", 16)),
            lora_alpha=int(lora.get("alpha", 32)),
            lora_dropout=float(lora.get("dropout", 0.05)),
            target_modules=list(lora.get("target_modules", ["q_proj", "v_proj"])),
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    max_len = int(config.get("max_seq_len", 4096))

    def tokenize(example: dict) -> dict:
        """Токены всего диалога; метки только для ответа ассистента, остальное — -100."""
        messages = example["messages"]
        prompt_text = tokenizer.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
        full_text = tokenizer.apply_chat_template(messages, tokenize=False)
        prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        full = tokenizer(full_text, add_special_tokens=False, truncation=True, max_length=max_len)
        labels = list(full["input_ids"])
        cut = min(len(prompt_ids), len(labels))
        labels[:cut] = [-100] * cut
        full["labels"] = labels
        return full

    dataset = Dataset.from_list(examples).map(tokenize, remove_columns=["messages", "id"])
    masked_only = sum(1 for row in dataset if all(t == -100 for t in row["labels"]))
    if masked_only:
        print(f"Внимание: у {masked_only} примеров ответ не поместился в max_seq_len={max_len} и будет проигнорирован")

    args_kwargs: dict = dict(
        output_dir=config["output_dir"],
        num_train_epochs=float(config.get("epochs", 2)),
        learning_rate=float(config.get("learning_rate", 1e-4)),
        per_device_train_batch_size=int(config.get("batch_size", 2)),
        gradient_accumulation_steps=int(config.get("gradient_accumulation", 8)),
        weight_decay=float(config.get("weight_decay", 0.0)),
        logging_steps=int(config.get("logging_steps", 10)),
        save_steps=int(config.get("save_steps", 200)),
        gradient_checkpointing=True,
        bf16=use_bf16,
        fp16=not use_bf16 and torch.cuda.is_available(),
        seed=int(config.get("seed", 42)),
        report_to=[],
    )
    warmup = float(config.get("warmup_ratio", 0.05))
    # transformers < 5: warmup_ratio; transformers >= 5: warmup_steps принимает долю (float < 1).
    if "warmup_ratio" in inspect.signature(TrainingArguments).parameters:
        args_kwargs["warmup_ratio"] = warmup
    else:
        args_kwargs["warmup_steps"] = warmup
    args = TrainingArguments(**args_kwargs)

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, label_pad_token_id=-100, padding=True),
    )
    trainer.train()
    model.save_pretrained(config["output_dir"])
    tokenizer.save_pretrained(config["output_dir"])
    print(f"Адаптер сохранён в {config['output_dir']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="training/lora_config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="проверить конфигурацию и данные, не обучая")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    examples = load_examples(config["dataset"])
    describe(examples)
    if args.dry_run:
        print("Dry run: обучение не запускалось")
        return 0
    train(config, examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
