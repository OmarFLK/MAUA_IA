from __future__ import annotations

import argparse
import json
from pathlib import Path


MINIMUM_VRAM_GB = 24


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a local SEMOB QLoRA adapter from local-only model files.")
    parser.add_argument("--model", type=Path, required=True, help="Local Gemma model directory; network downloads are disabled.")
    parser.add_argument("--train", type=Path, default=Path("data/finetuning/train.jsonl"))
    parser.add_argument("--validation", type=Path, default=Path("data/finetuning/validation.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/qlora-semob"))
    parser.add_argument("--max-length", type=int, default=4096)
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
            AutoConfig,
            AutoTokenizer,
            BitsAndBytesConfig,
            DataCollatorForSeq2Seq,
            Gemma3ForConditionalGeneration,
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
    config = AutoConfig.from_pretrained(args.model, local_files_only=True)
    if config.model_type != "gemma3":
        raise SystemExit("This recipe targets Gemma 3 4B/12B/27B. Verify the exact licensed base model with the Baro owner.")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True)
    model = Gemma3ForConditionalGeneration.from_pretrained(
        args.model,
        local_files_only=True,
        quantization_config=quantization,
        device_map="auto",
        torch_dtype=dtype,
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
            target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)",
        ),
    )
    dataset = load_dataset("json", data_files={"train": str(args.train), "validation": str(args.validation)})

    def tokenize(example: dict[str, object]) -> dict[str, object]:
        messages = example['messages']
        tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
        prefix = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True)
        if tokens[:len(prefix)] != prefix:
            raise ValueError('Chat template prefix mismatch; response masking would be incorrect')
        if len(tokens) > args.max_length:
            raise ValueError('Example exceeds max length; shorten/review it rather than truncating the answer')
        # Only the final assistant answer contributes to loss, not retrieved evidence or prompts.
        return {'input_ids': tokens, 'attention_mask': [1] * len(tokens),
                'labels': [-100] * len(prefix) + tokens[len(prefix):]}

    tokenized = dataset.map(tokenize, remove_columns=dataset["train"].column_names)
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
            bf16=dtype == torch.bfloat16,
            fp16=dtype == torch.float16,
            gradient_checkpointing=True,
            report_to="none",
            seed=2026,
        ),
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, label_pad_token_id=-100),
    )
    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    evaluation = trainer.evaluate()
    (args.output / "training_manifest.json").write_text(
        json.dumps({"trained": True, "adapter_active": False, "base_model": str(args.model.resolve()),
                    "vram_gb": round(vram_gb, 2), "seed": 2026, "validation": evaluation,
                    "train_examples": len(dataset['train']), "validation_examples": len(dataset['validation'])}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

