-- Storage photos 버킷 허용 열기 (화면에서 그림 올리기 · 올라온 목록 보기)
-- Supabase SQL Editor 에 통째로 붙여 넣고 Run.
-- 이미 올라온 그림은 건드리지 않는다. 몇 번을 다시 Run 해도 오류 없이 같은 상태가 된다.

begin;

-- 1. photos 버킷이 없으면 만든다 (이미 있으면 설정까지 그대로 둠)
--    비공개 버킷, 그림 파일만 받음
insert into storage.buckets (id, name, public, allowed_mime_types)
values ('photos', 'photos', false, array['image/png', 'image/jpeg', 'image/gif', 'image/webp'])
on conflict (id) do nothing;

-- 2. 허용: 같은 이름 규칙이 있으면 지우고 다시 만든다 (그래서 다시 Run 해도 "이미 있음" 오류가 나지 않음)
--    storage.objects 는 모든 버킷의 파일이 함께 있는 표라서, 규칙마다 photos 버킷으로 좁힌다

-- 올라온 목록 보기 (그림 내려받기 · 보기도 이 허용으로 된다)
drop policy if exists "photos 보기" on storage.objects;
create policy "photos 보기" on storage.objects
  for select to anon, authenticated using (bucket_id = 'photos');

-- 그림 올리기
drop policy if exists "photos 올리기" on storage.objects;
create policy "photos 올리기" on storage.objects
  for insert to anon, authenticated with check (bucket_id = 'photos');

commit;

-- 3. 확인: 아래 결과 표에 2줄(SELECT, INSERT)이 나오고, 버킷_있음 칸이 true 면 다 들어간 것
select
  p.policyname                    as 허용_이름,
  p.cmd                           as 할_수_있는_일,
  array_to_string(p.roles, ', ')  as 누구에게,
  exists (select 1 from storage.buckets b where b.id = 'photos') as 버킷_있음,
  (select b.public from storage.buckets b where b.id = 'photos')  as 버킷_공개
from pg_policies p
where p.schemaname = 'storage'
  and p.tablename = 'objects'
  and p.policyname in ('photos 보기', 'photos 올리기')
order by array_position(array['SELECT', 'INSERT'], p.cmd);
