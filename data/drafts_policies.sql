-- drafts 표 (실습 게시판 결과물) 권한·허용 열기
-- Supabase SQL Editor 에 통째로 붙여 넣고 Run.
-- 표와 안의 데이터는 건드리지 않는다. 몇 번을 다시 Run 해도 오류 없이 같은 상태가 된다.
-- 화면(anon 키)에서 읽기 · 넣기 · 고치기 · 지우기를 모두 할 수 있게 한다
-- (지금 화면이 쓰는 읽기 · 넣기도 함께 넣어 두어, 이 SQL 하나로 화면이 다 돌아가게 한다).

begin;

-- 1. 권한: 표에 손댈 수 있는 자격 (이미 있으면 그대로 둠)
grant select, insert, update, delete on public.drafts to anon, authenticated;

-- 2. 허용 규칙 켜기 (이미 켜져 있으면 그대로 둠)
alter table public.drafts enable row level security;

-- 3. 허용: 같은 이름 규칙이 있으면 지우고 다시 만든다 (그래서 다시 Run 해도 "이미 있음" 오류가 나지 않음)
drop policy if exists "drafts 읽기" on public.drafts;
create policy "drafts 읽기" on public.drafts
  for select to anon, authenticated using (true);

drop policy if exists "drafts 넣기" on public.drafts;
create policy "drafts 넣기" on public.drafts
  for insert to anon, authenticated with check (true);

drop policy if exists "drafts 고치기" on public.drafts;
create policy "drafts 고치기" on public.drafts
  for update to anon, authenticated using (true) with check (true);

drop policy if exists "drafts 지우기" on public.drafts;
create policy "drafts 지우기" on public.drafts
  for delete to anon, authenticated using (true);

commit;

-- 4. 확인: 아래 결과 표에 4줄이 나오고, 줄마다 권한 칸이 "있음" 이면 다 들어간 것
select
  p.policyname                                   as 허용_이름,
  p.cmd                                          as 할_수_있는_일,
  array_to_string(p.roles, ', ')                 as 누구에게,
  c.relrowsecurity                               as 허용규칙_켜짐,
  case when has_table_privilege('anon', 'public.drafts', p.cmd) then '있음' else '없음' end as anon_권한
from pg_policies p
join pg_class c on c.oid = 'public.drafts'::regclass
where p.schemaname = 'public'
  and p.tablename = 'drafts'
  and p.policyname in ('drafts 읽기', 'drafts 넣기', 'drafts 고치기', 'drafts 지우기')
order by array_position(array['SELECT', 'INSERT', 'UPDATE', 'DELETE'], p.cmd);
