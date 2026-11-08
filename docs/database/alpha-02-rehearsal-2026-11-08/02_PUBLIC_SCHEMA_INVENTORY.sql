-- 唯讀簡單盤點；只看定義與擁有者，不讀業務資料，不執行REVOKE。
BEGIN READ ONLY;
SELECT current_database() AS database,current_database()='life_world_alpha' AS correct_target;
SELECT e.extname,e.extversion,n.nspname AS schema,pg_get_userbyid(e.extowner) AS owner
 FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace ORDER BY n.nspname,e.extname;
SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner) AS owner
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relkind,c.relname;
SELECT p.oid::regprocedure AS routine,p.prokind,pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS security_definer
 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY p.oid::regprocedure::text;
COMMIT;
