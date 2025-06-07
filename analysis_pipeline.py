
import gc
import re
import logging
import numpy as np
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Any, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm
from transformers import pipeline
import torch

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pipeline_analysis.log')
    ]
)
logger = logging.getLogger(__name__)


class ModelType(Enum):
    FACT_CHECK = auto()
    SUMMARIZER = auto()
    SENTIMENT = auto()


@dataclass
class AnalysisResult:
    article_id: str
    title: str
    summary: str = ""
    sentiment: Dict[str, Union[str, float]] = None
    credibility: Dict[str, float] = None
    embedding: List[float] = None
    processing_time: float = 0.0
    success: bool = False
    error: str = ""
    model_versions: Dict[str, str] = None
    metadata: Dict[str, Any] = None

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def to_dict(self) -> Dict:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "summary": self.summary,
            "sentiment": self.sentiment,
            "credibility": self.credibility,
            "embedding": self.embedding,
            "processing_time": self.processing_time,
            "success": self.success,
            "error": self.error,
            "model_versions": self.model_versions,
            "metadata": self.metadata
        }


class NewsAnalysisPipeline:
    def __init__(self, max_workers=4, device=None):
        self.max_workers = max_workers
        self.device = device if device else "cuda" if torch.cuda.is_available() else "cpu"
        self.available_models = set()
        self.model_versions = {}
        logger.info(f"使用设备: {self.device}")
        self._initialize_models()

    def _initialize_models(self):
        model_config = {
            ModelType.FACT_CHECK: {
                'model': 'typeform/distilbert-base-uncased-mnli',
                'task': 'text-classification'
            },
            ModelType.SUMMARIZER: {
                'model': 'csebuetnlp/mT5_multilingual_XLSum',
                'task': 'summarization'
            },
            ModelType.SENTIMENT: {
                'model': 'uer/roberta-base-finetuned-jd-binary-chinese',
                'task': 'text-classification'
            }
        }

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._load_hf_model, m_type, cfg['task'], cfg['model']): m_type
                for m_type, cfg in model_config.items()
            }

            with tqdm(total=len(futures), desc="加载模型") as pbar:
                for future in as_completed(futures):
                    m_type = futures[future]
                    try:
                        model_name = future.result()
                        self.model_versions[m_type] = model_name
                        self.available_models.add(m_type)
                        logger.info(f"{m_type.name}模型加载成功: {model_name}")
                    except Exception as e:
                        logger.error(f"{m_type.name}模型加载失败: {str(e)}")
                    finally:
                        pbar.update(1)
                        gc.collect()

    def _load_hf_model(self, m_type: ModelType, task: str, model_name: str):
        pipe = pipeline(
            task,
            model=model_name,
            tokenizer=model_name,
            device=0 if self.device == "cuda" else -1
        )
        setattr(self, f"{m_type.name.lower()}_pipeline", pipe)
        return model_name

    def analyze_article(self, article: Dict[str, Any]) -> AnalysisResult:
        start_time = datetime.now()
        result = AnalysisResult(
            article_id=str(article.get("id", "")),
            title=article.get("metadata", {}).get("title", ""),
            model_versions={k.name: v for k, v in self.model_versions.items()},
            metadata=article.get("metadata", {})
        )

        try:
            raw_content = article.get("text", "")
            if not raw_content:
                raise ValueError("文章内容为空")

            cleaned_content = self._clean_baidu_content(raw_content)
            if len(cleaned_content) < 50:
                raise ValueError(f"有效内容过短({len(cleaned_content)}字符)")

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._generate_summary, cleaned_content): "summary",
                    executor.submit(self._check_credibility, cleaned_content): "credibility",
                    executor.submit(self._analyze_sentiment, cleaned_content): "sentiment"
                }

                for future in as_completed(futures):
                    task_type = futures[future]
                    try:
                        setattr(result, task_type, future.result())
                    except Exception as e:
                        logger.error(f"{task_type}分析失败: {str(e)}")
                        if task_type == "credibility":
                            result.credibility = {"contradiction": 0.0, "neutral": 1.0, "entailment": 0.0}
                        elif task_type == "sentiment":
                            result.sentiment = {"label": "neutral", "score": 0.0, "truncated_length": 0}

            result.success = True
        except Exception as e:
            result.error = str(e)
            result.success = False

        result.processing_time = (datetime.now() - start_time).total_seconds()
        return result

    def _clean_baidu_content(self, content: str) -> str:
        error_patterns = [
            r"We're sorry but",
            r"百度APP扫码查看",
            r"请在文中横线处补写恰当的语句",
            r"本题试卷来源",
            r"搜索试题"
        ]

        if any(re.search(pattern, content) for pattern in error_patterns):
            return ""

        cleaned = re.sub(r'<[^>]+>', '', content)
        cleaned = re.sub(r'[\x00-\x1F\x7F]', '', cleaned)
        cleaned = re.sub(r'\[\d+\]|\uff3b\d+\uff3d', '', cleaned)
        cleaned = re.sub(r'图片:.*?\]', '', cleaned)
        cleaned = re.sub(r'图片来源:.*', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # 移除所有视频相关描述
        content = re.sub(r'视频处理中.*?更换封面', '', content)
        content = re.sub(r'简介:.*?来源:', '', content)
        content = re.sub(r' \d+:\d+', '', content)  # 移除时间标记

        # 移除来源信息
        content = re.sub(r'来源:.*?(发布时间:)?.*?\n', '\n', content)


        if len(cleaned) < 50:
            return ""

        sentences = re.split(r'[\u3002！？!?.]', cleaned)
        unique_sentences = set(sentences)
        if len(unique_sentences) / len(sentences) < 0.5:
            return ""
        # 添加调试语句
        print("清洗后内容：", cleaned[:500])
        return cleaned

    def _generate_summary(self, text: str) -> str:
        if ModelType.SUMMARIZER not in self.available_models:
            return text[:150] + "..."

        try:
            chunks = [text[i:i + 1024] for i in range(0, len(text), 1024)]
            summaries = [
                self.summarizer_pipeline(
                    chunk,
                    max_length=256,
                    min_length=128,
                    num_beams=6,
                    length_penalty=1.5,
                    no_repeat_ngram_size=3,
                    truncation=True,
                    do_sample=False
                )[0]['summary_text'] for chunk in chunks
            ]
            return "".join(summaries)[:256]
        except Exception as e:
            logger.error(f"摘要生成失败: {str(e)}")
            return text[:150] + "..."

    def _check_credibility(self, text: str) -> Dict[str, float]:
        """
        使用事实核查模型分析文本可信度
        返回格式: {"contradiction": 0.0, "neutral": 1.0, "entailment": 0.0}
        """
        if ModelType.FACT_CHECK not in self.available_models:
            logger.warning("事实核查模型不可用，返回默认中性评分")
            return {"contradiction": 0.0, "neutral": 1.0, "entailment": 0.0}

        try:
            # 确保输入是字符串且不为空
            if not isinstance(text, str) or not text.strip():
                raise ValueError("输入文本无效")

            # 分段处理长文本（每段512字符）
            segments = [text[i:i + 512] for i in range(0, min(len(text), 2048), 512)]
            if not segments:
                return {"contradiction": 0.0, "neutral": 1.0, "entailment": 0.0}

            total_scores = {"contradiction": 0.0, "neutral": 0.0, "entailment": 0.0}
            valid_segments = 0

            for segment in segments:
                try:
                    # 确保输入格式正确
                    if not segment.strip():
                        continue

                    # 获取模型结果
                    result = self.fact_check_pipeline(
                        segment,
                        truncation=True,
                        max_length=512
                    )

                    # 处理不同返回格式
                    if isinstance(result, list) and len(result) > 0:
                        item = result[0]
                        if isinstance(item, dict):
                            # 新版transformers返回格式
                            label = item["label"].lower()
                            score = float(item["score"])
                        elif isinstance(item, list):
                            # 旧版可能返回格式
                            label = item[0]["label"].lower()
                            score = float(item[0]["score"])
                        else:
                            continue

                        # 累加分数
                        if label in total_scores:
                            total_scores[label] += score
                            valid_segments += 1

                except Exception as seg_error:
                    logger.warning(f"分段分析失败: {str(seg_error)}", exc_info=True)
                    continue

            # 计算平均分
            if valid_segments > 0:
                return {k: round(v / valid_segments, 4) for k, v in total_scores.items()}

            return {"contradiction": 0.0, "neutral": 1.0, "entailment": 0.0}

        except Exception as e:
            logger.error(f"事实核查失败: {str(e)}", exc_info=True)
            return {
                "contradiction": 0.0,
                "neutral": 1.0,
                "entailment": 0.0,
                "error": str(e)
            }



    def _analyze_sentiment(self, text: str) -> Dict[str, Union[str, float]]:
        if ModelType.SENTIMENT not in self.available_models:
            return {"label": "neutral", "score": 0.0, "truncated_length": 0}

        try:
            sentiment_pipeline = getattr(self, 'sentiment_pipeline', None)
            if sentiment_pipeline is None:
                raise ValueError("情感模型未加载")

            max_length = 512
            truncated_text = text[:max_length]
            result = sentiment_pipeline(truncated_text)[0]

            label_map = {
                "LABEL_0": "negative",
                "LABEL_1": "positive",
                "LABEL_2": "neutral"
            }

            mapped_label = label_map.get(result['label'], result['label'])

            return {
                "label": mapped_label,
                "score": float(result['score']),
                "sentiment": self._get_sentiment_emoji(mapped_label, result['score']),
                "truncated_length": len(truncated_text)
            }
        except Exception as e:
            logger.error(f"情感分析失败: {str(e)}")
            return {"label": "error", "score": 0.0, "truncated_length": 0}

    def _get_sentiment_emoji(self, label: str, score: float) -> str:
        if "positive" in label:
            return "非常积极" if score > 0.8 else "积极"
        elif "negative" in label:
            return "非常消极" if score > 0.8 else "消极"
        return "中性"

