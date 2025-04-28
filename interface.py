from transformers import pipeline, RobertaTokenizer, RobertaForMaskedLM

class OneCAgent:
    def __init__(self, model_dir="model/codebert-1c-finetuned"):
        # 这里可以根据你的模型路径调整
        try:
            self.tokenizer = RobertaTokenizer.from_pretrained(model_dir)
            self.model = RobertaForMaskedLM.from_pretrained(model_dir)
            self.pipe = pipeline("fill-mask", model=self.model, tokenizer=self.tokenizer)
        except Exception as e:
            print(f"模型加载失败: {e}")
            self.pipe = None

    def code_completion(self, prompt, top_k=3):
        if not self.pipe:
            return ["模型未加载"]
        if "<mask>" not in prompt:
            prompt = prompt.rstrip() + " <mask>"
        results = self.pipe(prompt, top_k=top_k)
        return [r['sequence'] for r in results]

    def check_syntax(self, code):
        errors = []
        if not code.strip().endswith("КонецПроцедуры") and "Процедура" in code:
            errors.append("缺少 КонецПроцедуры 结尾")
        return errors

    def answer_question(self, question, context=None):
        # 这里只做占位，后续可接入大模型API
        return "（此处为智能回答占位，可接入大模型API或本地生成）"