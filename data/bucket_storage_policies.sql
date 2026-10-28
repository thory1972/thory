-- 버킷 허용 열기 (화면에서 파일 올리기 · 올라온 목록 보기)
-- 고칠 것 없이 통째로 붙여 넣어 Run. 가장 최근에 만든 버킷에 허용을 넣는다.
-- 이미 올라온 파일은 건드리지 않는다. 몇 번을 다시 Run 해도 오류 없이 같은 상태가 된다.

-- 0. 버킷 고르기: 가장 최근에 만든 버킷 (아래 전부에 쓰인다)
--    다른 버킷에 넣고 싶으면 이 줄 대신 select set_config('my.bucket', '버킷이름', false); 로 바꾼다
select set_config('my.bucket', (select id from storage.buckets order by created_at desc limit 1), false);

do $$
declare
  b text := current_setting('my.bucket');
begin
  -- 1. 버킷이 정말 있는지 확인 (이름을 잘못 적었으면 여기서 멈추고 아무것도 바꾸지 않음)
  if not exists (select 1 from storage.buckets where id = b) then
    raise exception '버킷 "%" 을(를) 찾지 못했습니다. 맨 위 이름을 확인해 주세요.', b;
  end if;

  -- 2. 허용: 같은 이름 규칙이 있으면 지우고 다시 만든다 (그래서 다시 Run 해도 "이미 있음" 오류가 나지 않음)
  --    storage.objects 는 모든 버킷의 파일이 함께 있는 표라서, 규칙마다 이 버킷으로 좁힌다

  -- 올라온 목록 보기 (파일 내려받기도 이 허용으로 된다)
  execute format('drop policy if exists %I on storage.objects', b || ' 보기');
  execute format(
    'create policy %I on storage.objects for select to anon, authenticated using (bucket_id = %L)',
    b || ' 보기', b
  );

  -- 파일 올리기
  execute format('drop policy if exists %I on storage.objects', b || ' 올리기');
  execute format(
    'create policy %I on storage.objects for insert to anon, authenticated with check (bucket_id = %L)',
    b || ' 올리기', b
  );
end $$;

-- 3. 확인: 아래 결과 표에 2줄(SELECT, INSERT)이 나오고, 버킷_이름 칸이 방금 만든 버킷이면 다 들어간 것
select
  current_setting('my.bucket')    as 버킷_이름,
  p.policyname                   as 허용_이름,
  p.cmd                           as 할_수_있는_일,
  array_to_string(p.roles, ', ')  as 누구에게,
  (select bk.public from storage.buckets bk where bk.id = current_setting('my.bucket')) as 버킷_공개
from pg_policies p
where p.schemaname = 'storage'
  and p.tablename = 'objects'
  and p.policyname in (current_setting('my.bucket') || ' 보기', current_setting('my.bucket') || ' 올리기')
order by array_position(array['SELECT', 'INSERT'], p.cmd);
