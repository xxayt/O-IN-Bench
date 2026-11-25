SUBCATEGORIES = (
    'Direct Scene-based Request',
    'Spatial Reference',
    'Temporal Reference',
    'Multi-Speaker Attribution',
    'Addressee Shift Tracking',
    'Background Information Filtering',
    'Conditional Assistance',
    'Trouble Discernment',
    'Visual Contextual Reasoning',
    'Multimodal Emotion Recognition',
    'Request Revision Tracking',
    'Multimodal Constraint Integration',
    'Multi-Party Reconciliation',
    'Request Disambiguation',
    'Evidence Sufficiency Assessment',
    'False Premise Correction',
)

CATEGORIES = (
    "Situated Request Interpretation",
    "Interaction Management",
    "Implicit Intention Reasoning",
    "Request Integration",
    "Response Deliberation",
)
DIMENSIONS = ("language", "intent", "content")


# 仅在该分组全部判分成功时返回样本等权的百分制分数。
def group_score(rows):
    if not rows or any(row["status"] != "ok" for row in rows):
        return None
    return 100 * sum(row["score"] for row in rows) / len(rows)


# 汇总总分、三维通过率和两级类目分数，沉默样本仅参与意图维度。
def build_summary(rows):
    dimensions = {}
    for key in DIMENSIONS:
        judged = [row for row in rows if row["status"] == "ok"
                  and (key == "intent" or row["response_required"])]
        dimensions[key] = 100 * sum(row["scores"][key] for row in judged) / len(judged) if judged else None
    return {
        "score": group_score(rows),
        "dimensions": dimensions,
        "by_l1": {category: group_score([row for row in rows if row["task_l1"] == category])
                  for category in CATEGORIES},
        "by_subcategory": {subcategory: group_score([row for row in rows if row["task_l2"] == subcategory])
                           for subcategory in SUBCATEGORIES},
    }
