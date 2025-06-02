
import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MongoDBClient:
    def __init__(self):
        try:
            # 获取 MongoDB 连接信息
            mongo_uri = os.getenv("MONGO_URI")
            mongo_db = os.getenv("MONGO_DB")

            # 检查环境变量是否加载成功
            if not mongo_uri or not mongo_db:
                raise ValueError("环境变量 MONGO_URI 或 MONGO_DB 未正确加载")

            # 建立 MongoDB 连接
            self.client = MongoClient(mongo_uri)
            self.db = self.client[mongo_db]

            # 日志记录连接成功信息
            logging.info(f"MongoDB 连接成功: 数据库 {mongo_db} 已连接")
        except Exception as e:
            # 日志记录连接失败信息
            logging.error(f"MongoDB 连接失败: {e}")
            raise e  # 重新抛出异常，便于外部处理

    def get_unanalyzed_articles(self, limit=100):
        """获取未分析的原始文章"""
        try:
            collection_name = os.getenv("MONGO_COLLECTION")
            if not collection_name:
                raise ValueError("环境变量 MONGO_COLLECTION 未正确加载")

            # 查询未分析的文章
            articles = list(self.db[collection_name].find(
                {"analyzed": False},  # 查询条件：analyzed 字段为 False
                limit=limit
            ))
            logging.info(f"查询到 {len(articles)} 条未分析的文章")
            return articles
        except Exception as e:
            logging.error(f"获取未分析文章失败: {e}")
            raise e

    def save_analysis_result(self, article_id, result):
        """保存分析结果"""
        try:
            analysis_collection = os.getenv("ANALYSIS_COLLECTION")
            if not analysis_collection:
                raise ValueError("环境变量 ANALYSIS_COLLECTION 未正确加载")

            # 保存分析结果到分析集合
            self.db[analysis_collection].update_one(
                {"_id": ObjectId(article_id)},
                {"$set": result},
                upsert=True
            )
            logging.info(f"分析结果已保存到集合 {analysis_collection}，文章 ID: {article_id}")

            # 确保标记原始文章为已分析
            collection_name = os.getenv("MONGO_COLLECTION")
            self.db[collection_name].update_one(
                {"_id": ObjectId(article_id)},
                {"$set": {"analyzed": True}},
                upsert=False
            )
            logging.info(f"原始文章已标记为已分析，文章 ID: {article_id}")
        except Exception as e:
            logging.error(f"保存分析结果失败: {e}")
            raise e

    def move_article(self, article_id, result, success=True):
        """
        移动文章到成功或失败集合，删除原集合文章
        :param article_id: ObjectId 或字符串形式的文章ID
        :param result: 分析结果字典（包含文章内容和分析结果）
        :param success: True 移到 analyzed_succ，False 移到 analyzed_fail
        """
        try:
            # 转换 article_id 为 ObjectId
            if not isinstance(article_id, ObjectId):
                article_id = ObjectId(article_id)

            # 目标集合
            succ_collection = os.getenv("ANALYZED_SUCC_COLLECTION", "analyzed_succ")
            fail_collection = os.getenv("ANALYZED_FAIL_COLLECTION", "analyzed_fail")
            raw_collection = os.getenv("MONGO_COLLECTION")

            target_collection = succ_collection if success else fail_collection

            # 移除 _id 防止冲突（因为会自动生成新的_id）
            if "_id" in result:
                del result["_id"]

            # 补充状态和时间
            result["analyzed"] = success
            result["analyzed_at"] = datetime.utcnow()
            result["original_id"] = article_id  # 保留原始ID便于追踪

            # 插入目标集合
            self.db[target_collection].insert_one(result)
            logging.info(f"文章 {article_id} 已移动到集合 {target_collection}")

            # 删除原始集合中的文章
            self.db[raw_collection].delete_one({"_id": article_id})
            logging.info(f"文章 {article_id} 已从原始集合 {raw_collection} 中删除")

            return True
        except Exception as e:
            logging.error(f"移动文章失败: {e}")
            return False
