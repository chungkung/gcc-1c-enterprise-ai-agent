from transformers import RobertaTokenizer, RobertaForMaskedLM, Trainer, TrainingArguments, TextDataset, DataCollatorForLanguageModeling

model_name = "microsoft/codebert-base"
tokenizer = RobertaTokenizer.from_pretrained(model_name)
model = RobertaForMaskedLM.from_pretrained(model_name)

train_dataset = TextDataset(
    tokenizer=tokenizer,
    file_path="data/split/train.txt",
    block_size=128,
)
eval_dataset = TextDataset(
    tokenizer=tokenizer,
    file_path="data/split/val.txt",
    block_size=128,
)
data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer, mlm=True, mlm_probability=0.15
)
training_args = TrainingArguments(
    output_dir="./model/codebert-1c-finetuned",
    overwrite_output_dir=True,
    num_train_epochs=3,
    per_device_train_batch_size=8,
    save_steps=500,
    save_total_limit=2,
    prediction_loss_only=True,
)
trainer = Trainer(
    model=model,
    args=training_args,
    data_collator=data_collator,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
)
trainer.train()
