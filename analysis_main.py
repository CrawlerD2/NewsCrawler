# import os
# import time
# import json
# import logging
# from datetime import datetime
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from argparse import ArgumentParser
# from pymongo import MongoClient
# from dotenv import load_dotenv
# from tqdm import tqdm
# import psutil
# import gc
# import torch

# # 加载环境变量
# load_dotenv()

# # 配置日志
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler(),
#         logging.FileHandler('news_analysis.log', encoding='utf-8')
#     ]
# )
# logger = logging.getLogger(__name__)


# class MongoDBClient:
#     def __init__(self):
#         self.client = MongoClient(os.getenv("MONGO_URI"))
#         self.db = self.client[os.getenv("MONGO_DB")]
#         self.raw_collection = os.getenv("MONGO_COLLECTION", "raw_articles")
#         self.analysis_collection = os.getenv("ANALYSIS_COLLECTION", "analyzed_articles")

#     def get_unanalyzed_articles(self, limit=100):
#         """只获取必要字段，提高查询效率"""
#         articles = list(self.db[self.raw_collection].find(
#             {
#                 "$or": [
#                     {"analyzed": {"$exists": False}},
#                     {"analyzed": False}
#                 ],
#                 "news_content": {"$exists": True}
#             },
#             {
#                 "_id": 1,
#                 "news_content": 1,
#                 "hotsearch_title": 1,
#                 "source": 1,
#                 "publish_date": 1
#             },
#             sort=[("publish_date", -1)],
#             limit=limit
#         ))

#         # 打印每篇文章的内容（调试时用）
#         for article in articles:
#             print(f"文章ID: {article['_id']}")
#             print(f"标题: {article.get('hotsearch_title', '无标题')}")
#             print(f"内容: {article.get('news_content', '无内容')}")
#             print(f"来源: {article.get('source', '无来源')}")
#             print(f"发布日期: {article.get('publish_date', '无日期')}")
#             print("-" * 50)

#         logger.info(f"查询到 {len(articles)} 条未分析的文章")
#         return articles

#     def save_analysis_result(self, article_id, result):
#         try:
#             if "_id" in result:
#                 result.pop("_id")
#             update_fields = result.copy()
#             update_fields["analyzed"] = True
#             update_fields["analyzed_at"] = datetime.utcnow()

#             self.db[self.raw_collection].update_one(
#                 {"_id": article_id},
#                 {"$set": update_fields}
#             )
#             return True
#         except Exception as e:
#             logger.error(f"保存结果失败: {str(e)}")
#             return False

#     def move_article(self, article_id, result, success=True):
#         """
#         移动文章到成功或失败集合，删除原集合文章
#         """
#         try:
#             from bson import ObjectId
#             if not isinstance(article_id, ObjectId):
#                 article_id = ObjectId(article_id)

#             succ_collection = os.getenv("ANALYZED_SUCC_COLLECTION", "analyzed_succ")
#             fail_collection = os.getenv("ANALYZED_FAIL_COLLECTION", "analyzed_fail")
#             raw_collection = self.raw_collection

#             target_collection = succ_collection if success else fail_collection

#             if "_id" in result:
#                 del result["_id"]

#             result["analyzed"] = success
#             result["analyzed_at"] = datetime.utcnow()
#             result["original_id"] = article_id

#             self.db[target_collection].insert_one(result)
#             logger.info(f"文章 {article_id} 已移动到集合 {target_collection}")

#             self.db[raw_collection].delete_one({"_id": article_id})
#             logger.info(f"文章 {article_id} 已从原始集合 {raw_collection} 中删除")

#             return True
#         except Exception as e:
#             logger.error(f"移动文章失败: {e}")
#             return False


# def clean_memory():
#     """清理内存，尤其是GPU内存"""
#     gc.collect()
#     if torch.cuda.is_available():
#         torch.cuda.empty_cache()


# def process_article(pipeline, article):
#     try:
#         content_to_analyze = {
#             "id": str(article["_id"]),
#             "text": article.get("news_content", ""),
#             "metadata": {
#                 "title": article.get("hotsearch_title"),
#                 "source": article.get("source")
#             }
#         }
#         logger.debug(f"传递到分析函数的文章内容: {content_to_analyze['text']}")

#         result = pipeline.analyze_article(content_to_analyze)
#         logger.info(f"分析结果: {result}")

#         result_dict = result.__dict__ if hasattr(result, "__dict__") else dict(result)

#         # 附加原文章内容，方便存储
#         result_dict["news_content"] = article.get("news_content", "")
#         result_dict["hotsearch_title"] = article.get("hotsearch_title", "")
#         result_dict["source"] = article.get("source", "")
#         result_dict["publish_date"] = article.get("publish_date", None)

#         if getattr(result, "success", False):
#             if db_client.move_article(article["_id"], result_dict, success=True):
#                 logger.info(f"文章 {article['_id']} 分析成功并移动到 analyzed_succ")
#                 return True
#             else:
#                 logger.error(f"文章 {article['_id']} 分析成功但移动失败")
#                 return False
#         else:
#             if db_client.move_article(article["_id"], result_dict, success=False):
#                 logger.warning(f"文章 {article['_id']} 分析失败并移动到 analyzed_fail")
#             else:
#                 logger.error(f"文章 {article['_id']} 分析失败但移动失败")
#             return False

#     except Exception as e:
#         logger.error(f"处理文章 {article.get('_id')} 失败: {str(e)}")
#         fail_result = {
#             "error": str(e),
#             "news_content": article.get("news_content", ""),
#             "hotsearch_title": article.get("hotsearch_title", ""),
#             "source": article.get("source", ""),
#             "publish_date": article.get("publish_date", None),
#             "analyzed": False,
#             "analyzed_at": datetime.utcnow()
#         }
#         db_client.move_article(article["_id"], fail_result, success=False)
#         return False

#     finally:
#         clean_memory()


# def analyze_batch(batch_size=3, max_workers=4):
#     """分析一批文章"""
#     try:
#         from analysis_pipeline import NewsAnalysisPipeline

#         articles = db_client.get_unanalyzed_articles(limit=batch_size)
#         if not articles:
#             logger.info("没有未分析的文章")
#             return 0

#         logger.info(f"开始分析 {len(articles)} 篇文章...")
#         pipeline = NewsAnalysisPipeline()

#         success_count = 0
#         with ThreadPoolExecutor(max_workers=max_workers) as executor:
#             futures = {executor.submit(process_article, pipeline, article): article for article in articles}
#             for future in tqdm(as_completed(futures), total=len(futures), desc="分析进度"):
#                 if future.result():
#                     success_count += 1

#         logger.info(f"分析完成。成功: {success_count}/{len(articles)}")
#         return success_count

#     except Exception as e:
#         logger.error(f"批处理失败: {str(e)}", exc_info=True)
#         return 0


# def log_system_status():
#     """记录系统资源状态"""
#     mem = psutil.virtual_memory()
#     logger.info(
#         f"系统状态 - 内存: {mem.percent}% | "
#         f"CPU: {psutil.cpu_percent()}% | "
#         f"进程内存: {psutil.Process().memory_info().rss / 1024 / 1024:.1f}MB"
#     )


# def continuous_analysis(interval_minutes=30, batch_size=20, max_workers=4):
#     """持续分析循环"""
#     logger.info("启动持续分析服务...")
#     last_status_time = time.time()

#     while True:
#         try:
#             current_time = time.time()
#             if current_time - last_status_time > 3600:
#                 log_system_status()
#                 last_status_time = current_time

#             analyzed = db_client.db[db_client.raw_collection].count_documents({"analyzed": True})
#             total = db_client.db[db_client.raw_collection].count_documents({})
#             if total > 0:
#                 logger.info(f"分析进度: {analyzed}/{total} ({analyzed / total * 100:.1f}%)")

#             start_time = time.time()
#             analyze_batch(batch_size, max_workers)

#             elapsed = time.time() - start_time
#             sleep_time = max(interval_minutes * 60 - elapsed, 5)
#             logger.info(f"下次分析将在 {sleep_time / 60:.1f} 分钟后进行...")
#             time.sleep(sleep_time)

#         except KeyboardInterrupt:
#             logger.info("服务正常停止")
#             break
#         except Exception as e:
#             logger.error(f"服务异常: {str(e)}", exc_info=True)
#             time.sleep(60)


# if __name__ == "__main__":
#     db_client = MongoDBClient()

#     parser = ArgumentParser(description="新闻分析系统")
#     parser.add_argument("--batch-size", type=int, default=3, help="每批分析的文章数量")
#     parser.add_argument("--interval", type=int, default=30, help="持续分析间隔时间(分钟)")
#     parser.add_argument("--max-workers", type=int, default=4, help="最大线程数")
#     parser.add_argument("--single-run", action="store_true", help="单次运行模式")

#     args = parser.parse_args()

#     try:
#         if args.single_run:
#             logger.info("单次分析模式启动")
#             analyze_batch(args.batch_size, args.max_workers)
#         else:
#             continuous_analysis(args.interval, args.batch_size, args.max_workers)
#     except Exception as e:
#         logger.critical(f"系统崩溃: {str(e)}", exc_info=True)
#     finally:
#         clean_memory()
#         logger.info("系统服务终止")



import os
import time
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from argparse import ArgumentParser
from pymongo import MongoClient
from dotenv import load_dotenv
from tqdm import tqdm
import psutil
import gc
import torch

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('news_analysis.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class MongoDBClient:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.client[os.getenv("MONGO_DB")]
        self.raw_collection = os.getenv("MONGO_COLLECTION", "raw_articles")
        self.analysis_collection = os.getenv("ANALYSIS_COLLECTION", "analyzed_articles")

    def get_unanalyzed_articles(self, limit=100):
        """只获取必要字段，提高查询效率"""
        articles = list(self.db[self.raw_collection].find(
            {
                "$or": [
                    {"analyzed": {"$exists": False}},
                    {"analyzed": False}
                ],
                "news_content": {"$exists": True}
            },
            {
                "_id": 1,
                "news_content": 1,
                "hotsearch_title": 1,
                "source": 1,
                "publish_date": 1
            },
            sort=[("publish_date", -1)],
            limit=limit
        ))

        # 打印每篇文章的内容（调试时用）
        for article in articles:
            print(f"文章ID: {article['_id']}")
            print(f"标题: {article.get('hotsearch_title', '无标题')}")
            print(f"内容: {article.get('news_content', '无内容')}")
            print(f"来源: {article.get('source', '无来源')}")
            print(f"发布日期: {article.get('publish_date', '无日期')}")
            print("-" * 50)

        logger.info(f"查询到 {len(articles)} 条未分析的文章")
        return articles

    def save_analysis_result(self, article_id, result):
        try:
            if "_id" in result:
                result.pop("_id")
            update_fields = result.copy()
            update_fields["analyzed"] = True
            update_fields["analyzed_at"] = datetime.utcnow()

            self.db[self.raw_collection].update_one(
                {"_id": article_id},
                {"$set": update_fields}
            )
            return True
        except Exception as e:
            logger.error(f"保存结果失败: {str(e)}")
            return False

    def move_article(self, article_id, result, success=True):
        """
        移动文章到成功或失败集合，删除原集合文章
        """
        try:
            from bson import ObjectId
            if not isinstance(article_id, ObjectId):
                article_id = ObjectId(article_id)

            succ_collection = os.getenv("ANALYZED_SUCC_COLLECTION", "analyzed_succ")
            fail_collection = os.getenv("ANALYZED_FAIL_COLLECTION", "analyzed_fail")
            raw_collection = self.raw_collection

            target_collection = succ_collection if success else fail_collection

            if "_id" in result:
                del result["_id"]

            result["analyzed"] = success
            result["analyzed_at"] = datetime.utcnow()
            result["original_id"] = article_id

            self.db[target_collection].insert_one(result)
            logger.info(f"文章 {article_id} 已移动到集合 {target_collection}")

            self.db[raw_collection].delete_one({"_id": article_id})
            logger.info(f"文章 {article_id} 已从原始集合 {raw_collection} 中删除")

            return True
        except Exception as e:
            logger.error(f"移动文章失败: {e}")
            return False


def clean_memory():
    """清理内存，尤其是GPU内存"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def process_article(pipeline, article):
    try:
        content_to_analyze = {
            "id": str(article["_id"]),
            "text": article.get("news_content", ""),
            "metadata": {
                "title": article.get("hotsearch_title"),
                "source": article.get("source")
            }
        }
        logger.debug(f"传递到分析函数的文章内容: {content_to_analyze['text']}")

        result = pipeline.analyze_article(content_to_analyze)
        logger.info(f"分析结果: {result}")

        result_dict = result.__dict__ if hasattr(result, "__dict__") else dict(result)

        # 附加原文章内容，方便存储
        result_dict["news_content"] = article.get("news_content", "")
        result_dict["hotsearch_title"] = article.get("hotsearch_title", "")
        result_dict["source"] = article.get("source", "")
        result_dict["publish_date"] = article.get("publish_date", None)

        if getattr(result, "success", False):
            if db_client.move_article(article["_id"], result_dict, success=True):
                logger.info(f"文章 {article['_id']} 分析成功并移动到 analyzed_succ")
                return True
            else:
                logger.error(f"文章 {article['_id']} 分析成功但移动失败")
                return False
        else:
            if db_client.move_article(article["_id"], result_dict, success=False):
                logger.warning(f"文章 {article['_id']} 分析失败并移动到 analyzed_fail")
            else:
                logger.error(f"文章 {article['_id']} 分析失败但移动失败")
            return False

    except Exception as e:
        logger.error(f"处理文章 {article.get('_id')} 失败: {str(e)}")
        fail_result = {
            "error": str(e),
            "news_content": article.get("news_content", ""),
            "hotsearch_title": article.get("hotsearch_title", ""),
            "source": article.get("source", ""),
            "publish_date": article.get("publish_date", None),
            "analyzed": False,
            "analyzed_at": datetime.utcnow()
        }
        db_client.move_article(article["_id"], fail_result, success=False)
        return False

    finally:
        clean_memory()


def analyze_batch(batch_size=3, max_workers=4):
    """分析一批文章"""
    try:
        from analysis_pipeline import NewsAnalysisPipeline

        articles = db_client.get_unanalyzed_articles(limit=batch_size)
        if not articles:
            logger.info("没有未分析的文章")
            return 0

        logger.info(f"开始分析 {len(articles)} 篇文章...")
        pipeline = NewsAnalysisPipeline()

        success_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_article, pipeline, article): article for article in articles}
            for future in tqdm(as_completed(futures), total=len(futures), desc="分析进度"):
                if future.result():
                    success_count += 1

        logger.info(f"分析完成。成功: {success_count}/{len(articles)}")
        return success_count

    except Exception as e:
        logger.error(f"批处理失败: {str(e)}", exc_info=True)
        return 0


def log_system_status():
    """记录系统资源状态"""
    mem = psutil.virtual_memory()
    logger.info(
        f"系统状态 - 内存: {mem.percent}% | "
        f"CPU: {psutil.cpu_percent()}% | "
        f"进程内存: {psutil.Process().memory_info().rss / 1024 / 1024:.1f}MB"
    )


if __name__ == "__main__":
    db_client = MongoDBClient()

    parser = ArgumentParser(description="新闻分析系统")
    parser.add_argument("--batch-size", type=int, default=10, help="每批分析的文章数量")
    parser.add_argument("--max-workers", type=int, default=4, help="最大线程数")

    args = parser.parse_args()

    try:
        logger.info("单次分析模式启动")
        analyze_batch(args.batch_size, args.max_workers)
    except Exception as e:
        logger.critical(f"系统崩溃: {str(e)}", exc_info=True)
    finally:
        clean_memory()
        logger.info("分析任务完成")





