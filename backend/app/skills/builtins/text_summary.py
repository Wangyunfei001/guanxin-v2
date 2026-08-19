"""文本摘要技能。"""

import re
from typing import Any, Dict, List

from app.models.skill import SkillMetadata, SkillParam, SkillResult, SkillType
from app.models.skill_context import SkillContext
from app.skills.base import BaseSkill


class TextSummarySkill(BaseSkill):
    """文本摘要技能：基于关键词提取的简单文本摘要。"""

    def _define_metadata(self) -> SkillMetadata:
        """定义技能元数据。"""
        return SkillMetadata(
            name="text_summary",
            display_name="文本摘要",
            description="对输入文本进行摘要，提取关键句子和关键词。",
            skill_type=SkillType.BUILTIN,
            params=[
                SkillParam(
                    name="text",
                    type="string",
                    description="待摘要的文本内容",
                    required=True,
                ),
                SkillParam(
                    name="max_sentences",
                    type="number",
                    description="最大摘要句子数",
                    required=False,
                    default=3,
                ),
            ],
            tags=["文本处理", "摘要"],
            category="text",
        )

    async def execute(
        self,
        params: Dict[str, Any],
        context: SkillContext,
    ) -> SkillResult:
        """执行文本摘要。"""
        text: str = params.get("text", "")
        max_sentences: int = int(params.get("max_sentences", 3))

        if not text.strip():
            return SkillResult(success=False, error="文本为空")

        # 分句
        sentences = self._split_sentences(text)
        if not sentences:
            return SkillResult(success=False, error="无法提取句子")

        # 计算词频
        word_freq = self._compute_word_freq(text)

        # 按句子得分排序
        scored_sentences = []
        for i, sent in enumerate(sentences):
            score = self._score_sentence(sent, word_freq)
            scored_sentences.append((i, sent, score))

        # 取 top N 句子（按原文顺序）
        top_sentences = sorted(scored_sentences, key=lambda x: x[2], reverse=True)
        selected = sorted(top_sentences[:max_sentences], key=lambda x: x[0])

        summary = "。".join([s[1] for s in selected]) + "。"
        keywords = [w for w, _ in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]]

        return SkillResult(
            success=True,
            output={
                "summary": summary,
                "keywords": keywords,
                "original_length": len(text),
                "summary_length": len(summary),
                "sentence_count": len(selected),
            },
            metadata={"skill": "text_summary"},
        )

    def _split_sentences(self, text: str) -> List[str]:
        """中文分句。"""
        # 按中文句号、问号、感叹号分句
        sentences = re.split(r"[。！？\.\!\?]+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _compute_word_freq(self, text: str) -> Dict[str, int]:
        """计算词频（简单实现：按双字组）。"""
        freq: Dict[str, int] = {}
        # 去除标点
        clean = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", text)
        for i in range(len(clean) - 1):
            bigram = clean[i : i + 2]
            if len(bigram) == 2:
                freq[bigram] = freq.get(bigram, 0) + 1
        return freq

    def _score_sentence(self, sentence: str, word_freq: Dict[str, int]) -> float:
        """计算句子得分。"""
        clean = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", sentence)
        score = 0.0
        for i in range(len(clean) - 1):
            bigram = clean[i : i + 2]
            score += word_freq.get(bigram, 0)
        # 归一化
        return score / max(len(clean), 1)
