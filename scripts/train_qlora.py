from __future__ import annotations

import argparse
import json
from pathlib import Path


MINIMUM_VRAM_GB = 24


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a local SEMOB QLoRA adapter from local-only model files.")
    parser.add_argument("--model", type=Path, required=True, help="Local Gemma model directory; network downloads are disabled.")
    parser.add_argument("--train", type=Path, default=Path("data/training/train.jsonl"))
    parser.add_argument("--validation", type=Path, default=Path("data/training/validation.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/qlora-semob"))
    args = parser.parse_args()

    if not args.model.is_dir():
        raise SystemExit(f"Local model directory not found: {args.model}")
    if not args.train.is_file() or not args.validation.is_file():
        raise SystemExit("Training data not found. Run: python -m scripts.prepare_finetuning")

    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit("Training dependencies are missing. Install requirements-training.txt in a dedicated CUDA environment.") from exc

    if not torch.cuda.is_available():
        raise SystemExit("QLoRA blocked: no CUDA GPU is available on this machine.")
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    if vram_gb < MINIMUM_VRAM_GB:
        raise SystemExit(f"QLoRA blocked: {vram_gb:.1f} GB VRAM detected; this 27B recipe requires at least {MINIMUM_VRAM_GB} GB.")

    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    if not tokenizer.chat_template:
        raise SystemExit("The local tokenizer has no chat template; obtain the exact template from the model owner.")
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        local_files_only=True,
        quantization_config=quantization,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ),
    )
    dataset = load_dataset("json", data_files={"train": str(args.train), "validation": str(args.validation)})

    def tokenize(batch: dict[str, object]) -> dict[str, object]:
        texts = [tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False) for messages in batch["messages"]]  # type: ignore[index]
        return tokenizer(texts, truncation=True, max_length=2048)

    tokenized = dataset.map(tokenize, batched=True, remove_columns=dataset["train"].column_names)
    args.output.mkdir(parents=True, exist_ok=True)
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(args.output),
            num_train_epochs=3,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=16,
            learning_rate=2e-4,
            logging_steps=1,
            eval_strategy="epoch",
            save_strategy="epoch",
            bf16=True,
            gradient_checkpointing=True,
            report_to="none",
            seed=2026,
        ),
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    trainer.save_model(args.output)
    (args.output / "training_manifest.json").write_text(
        json.dumps({"base_model": str(args.model.resolve()), "vram_gb": round(vram_gb, 2), "seed": 2026}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

