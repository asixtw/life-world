-- 用量以目標當地日期生效；舊欄位、實際貢獻及積分不重寫。
CREATE TABLE habit_quantity_versions (
    action_id TEXT NOT NULL REFERENCES actions(id),
    effective_from TEXT NOT NULL,
    quantity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (action_id, effective_from)
);

-- 未設定開始日的舊目標只保存「原始標準」，不猜測挑戰日期。
INSERT INTO habit_quantity_versions(action_id,effective_from,quantity,created_at)
SELECT a.id,COALESCE(g.start_date,'0001-01-01'),a.per_occurrence,g.created_at
FROM actions a JOIN goals g ON g.id=a.goal_id;
