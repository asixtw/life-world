-- 僅供既有受控管理連線內部監控；不掛一般帳號API，不讀AI原文/Key，不GRANT。
BEGIN READ ONLY;
SELECT count(*) AS reserved_calls,
 COALESCE(sum((response::jsonb->>'reservation_microusd')::bigint),0) AS reserved_microusd
FROM lw_core_draft.requests WHERE operation='ai_attempt_v1';
SELECT count(*) AS result_receipts,
 count(*) FILTER (WHERE response::jsonb->>'status'='failed') AS failed_calls,
 count(*) FILTER (WHERE response::jsonb->>'cost_microusd' IS NULL) AS unknown_cost_calls,
 sum((response::jsonb->>'cost_microusd')::bigint) AS provider_reported_cost_microusd,
 sum((response::jsonb->>'input_tokens')::bigint) AS reported_input_tokens,
 sum((response::jsonb->>'output_tokens')::bigint) AS reported_output_tokens
FROM lw_core_draft.requests WHERE operation='ai_result_v1';
-- 預留及供應商回報都不是實際帳單；未完成預留也要計入控制，不當成0。
COMMIT;
