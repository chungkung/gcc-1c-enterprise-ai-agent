import os
from transformers import pipeline, RobertaTokenizer, RobertaForMaskedLM
import openai

# 设置OpenAI API Key
openai.api_key = "sk-tH7IkrtohhMnRJVd2LjoRjyYIRKLCNwflMLjGFwSTG7zP7Sv"

class OneCAgent:
    def __init__(self, model_dir="model/codebert-1c-finetuned"):
        try:
            self.tokenizer = RobertaTokenizer.from_pretrained(model_dir)
            self.model = RobertaForMaskedLM.from_pretrained(model_dir)
            self.pipe = pipeline("fill-mask", model=self.model, tokenizer=self.tokenizer)
        except Exception as e:
            print(f"模型加载失败: {e}")
            self.pipe = None
        # 简单本地业务知识库
        self.knowledge_base = [
            {
                "question": "1C:Enterprise 如何定义过程",
                "answer": "使用 Процедура ... КонецПроцедуры 结构定义过程。例如：\nПроцедура МояПроцедура()\n    // 代码\nКонецПроцедуры"
            },
            {
                "question": "1C:Enterprise 如何调用过程",
                "answer": "直接使用过程名和参数调用。例如：\nМояПроцедура();"
            },
            {
                "question": "1C:Enterprise 常见语法错误",
                "answer": "常见错误包括：缺少 КонецПроцедуры、拼写错误、括号不匹配等。"
            }
        ]

    def code_completion(self, prompt, top_k=3):
        # 优先本地模型
        if self.pipe:
            if "<mask>" not in prompt:
                prompt = prompt.rstrip() + " <mask>"
            results = self.pipe(prompt, top_k=top_k)
            return [r['sequence'] for r in results]
        # 本地模型未加载，调用GPT-4o
        try:
            completion_prompt = f"请补全以下1C:Enterprise代码片段：\n{prompt}"
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": completion_prompt}],
                temperature=0.2,
                max_tokens=128
            )
            return [response.choices[0].message.content.strip()]
        except Exception as e:
            return [f"调用GPT-4o失败: {e}"]

    def check_syntax(self, code):
        import re
        errors = []
        # 检查过程结尾
        if "Процедура" in code and "КонецПроцедуры" not in code:
            errors.append("缺少 КонецПроцедуры 结尾")
        # 检查常见关键字
        if not re.search(r"Процедура\\s+\\w+\\(", code):
            errors.append("未检测到有效的过程定义")
        # 检查括号匹配
        if code.count('(') != code.count(')'):
            errors.append("括号数量不匹配")
        return errors

    def answer_question(self, question, context=None):
        # 先查本地知识库
        for item in self.knowledge_base:
            if item["question"] in question:
                return item["answer"]
        # 本地知识库无答案，调用GPT-4o
        try:
            prompt = f"你是1C:Enterprise编程专家。{('上下文：' + context) if context else ''} 问题：{question}"
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=256
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"调用GPT-4o失败: {e}" 