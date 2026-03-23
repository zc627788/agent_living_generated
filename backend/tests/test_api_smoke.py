"""后端冒烟测试。

覆盖健康检查、知识库运维、会话主链路、SSE 输出和图谱索引接口，保证核心能力至少能连通。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ReferenceCard
from app.services.interview import InterviewResult


class ApiSmokeTest(unittest.TestCase):
    def test_health_session_and_knowledge_flow(self) -> None:
        """验证最常用的 JSON 接口主路径。"""
        session_payload = {
            "initial_message": (
                "我要做一个春节抽奖活动专题页，活动时间是 2026/01/20 到 2026/02/05，"
                "奖品包括限定皮肤和周边，风格偏国风，专题后缀 spring-festival。"
            )
        }

        with TestClient(app) as client:
            health_response = client.get("/api/v1/health")
            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(health_response.json()["status"], "ok")
            self.assertIn("llm_model", health_response.json())

            list_response = client.get("/api/v1/knowledge/documents")
            self.assertEqual(list_response.status_code, 200)
            self.assertGreaterEqual(len(list_response.json()), 1)

            builtin_document_id = list_response.json()[0]["id"]
            detail_response = client.get(f"/api/v1/knowledge/documents/{builtin_document_id}")
            self.assertEqual(detail_response.status_code, 200)
            self.assertIn("content", detail_response.json())

            upload_response = client.post(
                "/api/v1/knowledge/upload",
                data={
                    "title": "测试上传文档",
                    "source_type": "case",
                    "source": "自动化测试",
                    "tags": "activity, test",
                    "url": "https://example.com/uploaded",
                    "thumbnail_url": "https://placehold.co/640x360/png?text=Upload",
                },
                files={
                    "file": (
                        "upload.txt",
                        "# 测试文档\n## 背景\n这是自动化测试写入的知识内容。\n## 规则\n需要保留上下文连续性。",
                        "text/plain; charset=utf-8",
                    )
                },
            )
            self.assertEqual(upload_response.status_code, 200)
            uploaded_document = upload_response.json()
            uploaded_document_id = uploaded_document["id"]

            update_response = client.put(
                f"/api/v1/knowledge/documents/{uploaded_document_id}",
                json={
                    "title": "测试上传文档-更新版",
                    "source_type": "case",
                    "source": "自动化测试",
                    "tags": ["activity", "test", "updated"],
                    "url": "https://example.com/uploaded-updated",
                    "thumbnail_url": "https://placehold.co/640x360/png?text=Updated",
                    "content": "# 测试文档\n## 背景\n更新后的内容。\n## 规则\n单文档重建索引必须成功。",
                },
            )
            self.assertEqual(update_response.status_code, 200)
            self.assertEqual(update_response.json()["title"], "测试上传文档-更新版")

            versions_response = client.get(
                f"/api/v1/knowledge/documents/{uploaded_document_id}/versions"
            )
            self.assertEqual(versions_response.status_code, 200)
            versions = versions_response.json()
            self.assertGreaterEqual(len(versions), 2)

            restore_response = client.post(
                f"/api/v1/knowledge/documents/{uploaded_document_id}/versions/{versions[-1]['id']}/restore"
            )
            self.assertEqual(restore_response.status_code, 200)
            self.assertEqual(restore_response.json()["id"], uploaded_document_id)

            reindex_response = client.post(f"/api/v1/knowledge/documents/{uploaded_document_id}/reindex")
            self.assertEqual(reindex_response.status_code, 200)

            chunk_response = client.get(f"/api/v1/knowledge/chunks?document_id={uploaded_document_id}")
            self.assertEqual(chunk_response.status_code, 200)
            self.assertGreaterEqual(len(chunk_response.json()), 1)

            job_response = client.post(
                "/api/v1/knowledge/jobs/reindex",
                json={"document_ids": [uploaded_document_id]},
            )
            self.assertEqual(job_response.status_code, 200)
            job = job_response.json()
            self.assertEqual(job["job_type"], "batch_reindex")
            self.assertEqual(job["document_ids"], [uploaded_document_id])

            job_detail_response = client.get(f"/api/v1/knowledge/jobs/{job['id']}")
            self.assertEqual(job_detail_response.status_code, 200)
            self.assertEqual(job_detail_response.json()["id"], job["id"])

            session_response = client.post("/api/v1/sessions", json=session_payload)
            self.assertEqual(session_response.status_code, 200)

            session = session_response.json()["session"]
            self.assertEqual(session["topic_type"], "activity")
            self.assertGreaterEqual(len(session["missing_slots"]), 1)
            self.assertTrue(session["references"])

            export_response = client.get(f"/api/v1/sessions/{session['id']}/export/docx")
            self.assertEqual(export_response.status_code, 200)
            self.assertIn(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                export_response.headers["content-type"],
            )
            self.assertIn("X-Storage-Key", export_response.headers)

            delete_response = client.delete(f"/api/v1/knowledge/documents/{uploaded_document_id}")
            self.assertEqual(delete_response.status_code, 200)

    def test_stream_session_and_graph_index_routes(self) -> None:
        """验证 SSE 路由和 GraphRAG 索引列表接口。"""
        with TestClient(app) as client:
            fake_result = InterviewResult(
                title="版本上线专题",
                topic_type="display",
                slots={
                    "活动名称": "版本上线专题",
                    "活动时间": "2026/03/01 - 2026/03/20",
                    "核心卖点": "新角色、预约福利、剧情亮点",
                    "目标用户": "活跃玩家",
                    "风格关键词": "未来感",
                    "URL后缀": "version-launch",
                },
                missing_slots=[],
                risk_alerts=["请确认最终上线时间边界。"],
                references=[
                    ReferenceCard(
                        id="ref-1",
                        title="版本专题参考",
                        source="测试源",
                        source_type="case",
                        snippet="版本专题参考片段",
                        score=0.88,
                        section_path="概览",
                        tags=["display"],
                    )
                ],
                assistant_message="我已经整理出一版版本上线专题 PRD。",
                prd_markdown="# 版本上线专题\n\n- 核心卖点：新角色、预约福利、剧情亮点",
            )

            with patch(
                "app.api.routes.interview_service.stream",
                return_value=iter(
                    [
                        {"event": "status", "data": {"node": "router", "message": "语义路由完成"}},
                        {"event": "delta", "data": {"content": "我已经整理出一版"}},
                        {"event": "result", "data": fake_result},
                    ]
                ),
            ):
                stream_response = client.post(
                    "/api/v1/sessions/stream",
                    json={
                        "initial_message": "我要做一个版本上线专题页，突出新角色和预约按钮。",
                        "retrieval": {
                            "limit": 4,
                            "candidate_multiplier": 2,
                            "keyword_weight": 0.06,
                            "neighbor_hops": 1,
                            "min_score": 0.1,
                            "use_query_rewrite": True,
                        },
                    },
                )
            self.assertEqual(stream_response.status_code, 200)
            self.assertIn("event: session", stream_response.text)
            self.assertIn("event: done", stream_response.text)

            graph_indexes_response = client.get("/api/v1/knowledge/graph/indexes")
            self.assertEqual(graph_indexes_response.status_code, 200)
            self.assertIsInstance(graph_indexes_response.json(), list)


if __name__ == "__main__":
    unittest.main()
