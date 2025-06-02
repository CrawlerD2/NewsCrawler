import os
import logging
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
from bson import ObjectId
from typing import List, Dict, Any, Optional

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('article_analysis.log')
    ]
)
logger = logging.getLogger(__name__)


class MongoDBClient:
    def __init__(self):
        """初始化 MongoDB 客户端并确保索引存在"""
        try:
            # 获取 MongoDB 连接信息
            self.mongo_uri = os.getenv("MONGO_URI")
            self.mongo_db = os.getenv("MONGO_DB")
            self.collection_name = os.getenv("MONGO_COLLECTION")
            self.analysis_collection = os.getenv("ANALYSIS_COLLECTION")

            # 验证环境变量
            if not all([self.mongo_uri, self.mongo_db, self.collection_name, self.analysis_collection]):
                raise ValueError("必需的环境变量未正确加载")

            # 建立 MongoDB 连接
            self.client = MongoClient(
                self.mongo_uri,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.client[self.mongo_db]

            # 确保索引存在
            self._ensure_indexes()

            logger.info(f"成功连接到 MongoDB 数据库: {self.mongo_db}")
        except Exception as e:
            logger.error(f"MongoDB 连接失败: {e}")
            raise

    def _ensure_indexes(self):
        """确保必要的索引存在"""
        try:
            # 为 analyzed 字段创建索引以提高查询性能
            self.db[self.collection_name].create_index(
                [("analyzed", ASCENDING)],
                background=True,
                name="analyzed_index"
            )
            logger.info("已确保必要的索引存在")
        except Exception as e:
            logger.warning(f"创建索引时出错: {e}")

    def get_unanalyzed_articles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取未分析的原始文章（包括没有 analyzed 字段的文章）

        参数:
            limit: 返回的最大文章数量

        返回:
            未分析的文章列表
        """
        try:
            # 查询未分析的文章（analyzed=False 或 analyzed 字段不存在）
            query = {
                "$or": [
                    {"analyzed": False},
                    {"analyzed": {"$exists": False}}
                ]
            }

            articles = list(
                self.db[self.collection_name].find(
                    query,
                    limit=limit,
                    # 只返回必要的字段，减少网络传输
                    projection={"title": 1, "content": 1, "published_at": 1}
                )
            )

            logger.info(f"查询到 {len(articles)} 条未分析的文章")
            return articles
        except Exception as e:
            logger.error(f"获取未分析文章失败: {e}")
            raise

    def save_analysis_result(
            self,
            article_id: str,
            result: Dict[str, Any],
            batch_mode: bool = False
    ) -> bool:
        """
        保存分析结果并标记文章为已分析

        参数:
            article_id: 文章ID
            result: 分析结果字典
            batch_mode: 是否为批量模式（不记录详细日志）

        返回:
            操作是否成功
        """
        try:
            # 转换ID为ObjectId
            obj_id = ObjectId(article_id)

            # 使用事务确保数据一致性
            with self.client.start_session() as session:
                with session.start_transaction():
                    # 保存分析结果
                    self.db[self.analysis_collection].update_one(
                        {"_id": obj_id},
                        {"$set": result},
                        upsert=True,
                        session=session
                    )

                    # 标记原始文章为已分析
                    self.db[self.collection_name].update_one(
                        {"_id": obj_id},
                        {"$set": {"analyzed": True}},
                        upsert=False,
                        session=session
                    )

            if not batch_mode:
                logger.info(f"成功保存分析结果并标记文章 {article_id} 为已分析")
            return True
        except Exception as e:
            logger.error(f"保存分析结果失败 (文章ID: {article_id}): {e}")
            return False

    def batch_save_results(
            self,
            article_results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        批量保存分析结果

        参数:
            article_results: 包含文章ID和分析结果的字典列表

        返回:
            包含成功和失败计数的字典
        """
        success_count = 0
        failure_count = 0

        for item in article_results:
            if self.save_analysis_result(
                    item["article_id"],
                    item["result"],
                    batch_mode=True
            ):
                success_count += 1
            else:
                failure_count += 1

        logger.info(
            f"批量保存完成 - 成功: {success_count}, 失败: {failure_count}"
        )
        return {
            "success": success_count,
            "failure": failure_count
        }

    def close(self):
        """关闭 MongoDB 连接"""
        try:
            self.client.close()
            logger.info("MongoDB 连接已关闭")
        except Exception as e:
            logger.error(f"关闭连接时出错: {e}")


def main():
    """主处理函数"""
    try:
        # 创建 MongoDBClient 实例
        db_client = MongoDBClient()

        # 获取未分析的文章
        articles = db_client.get_unanalyzed_articles(limit=10)

        if not articles:
            logger.info("没有未分析的文章可供处理")
            return

        logger.info(f"开始处理 {len(articles)} 篇文章...")

        # 处理每篇文章
        for article in articles:
            article_id = str(article["_id"])

            try:
                # 模拟分析过程
                analysis_result = {
                    "score": 85,  # 假设的分析分数
                    "summary": "这是文章摘要",  # 假设的摘要
                    "keywords": ["关键词1", "关键词2"],  # 假设的关键词
                    "analysis_date": datetime.utcnow()  # 分析时间
                }

                # 保存分析结果
                if db_client.save_analysis_result(article_id, analysis_result):
                    logger.debug(f"成功处理文章 {article_id}")
                else:
                    logger.warning(f"处理文章 {article_id} 失败")

            except Exception as e:
                logger.error(f"处理文章 {article_id} 时发生异常: {e}")
                continue

    except Exception as e:
        logger.critical(f"主处理流程失败: {e}")
    finally:
        db_client.close()


if __name__ == "__main__":
    from datetime import datetime

    main()
