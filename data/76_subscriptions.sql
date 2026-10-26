-- subscriptions 표 만들기 (data/76_subscriptions.csv 12줄을 그대로 넣음)
-- Supabase SQL Editor 에 통째로 붙여 넣고 Run.
-- 다시 Run 하면 표를 지우고 새로 만들어서, 화면에서 넣고·고치고·지운 것이 모두 사라지고 처음 12줄로 돌아온다.

begin;

-- 1. 있던 표를 지운다 (표에 붙은 허용 규칙도 함께 지워짐)
drop table if exists public.subscriptions;

-- 2. 표 만들기 (CSV 4열 + 줄 번호 id, 만든 때 created_at)
create table public.subscriptions (
  id          bigint generated always as identity primary key,
  name        text    not null,              -- 구독 이름
  category    text    not null,              -- 분류
  monthly_fee integer not null,              -- 한 달 요금 (원)
  last_used   date,                          -- 마지막으로 쓴 날
  created_at  timestamptz not null default now()
);

-- 3. 허용: 화면(anon 키)에서 읽기 · 넣기 · 고치기 · 지우기
alter table public.subscriptions enable row level security;

grant select, insert, update, delete on public.subscriptions to anon, authenticated;

create policy "읽기" on public.subscriptions
  for select to anon, authenticated using (true);

create policy "넣기" on public.subscriptions
  for insert to anon, authenticated with check (true);

create policy "고치기" on public.subscriptions
  for update to anon, authenticated using (true) with check (true);

create policy "지우기" on public.subscriptions
  for delete to anon, authenticated using (true);

-- 4. 처음 데이터 (CSV 순서 그대로)
insert into public.subscriptions (name, category, monthly_fee, last_used) values
  ('영화 · 드라마 구독', '영상',     13500,  '2026-10-18'),
  ('음악 구독',          '음악',     10900,  '2026-10-20'),
  ('클라우드 저장공간',  '업무',      2400,  '2026-10-19'),
  ('헬스장',             '운동',     55000,  '2026-03-02'),
  ('신문 구독',          '읽을거리', 150000, '2026-10-21'),
  ('우유 배달',          '먹거리',   18000,  '2026-10-21'),
  ('정수기 렌털',        '생활',     23900,  '2026-10-21'),
  ('꽃 정기배송',        '생활',     19800,  '2026-09-28'),
  ('전자책 구독',        '읽을거리',  9900,  '2026-08-15'),
  ('반찬 정기배송',      '먹거리',   64000,  '2026-10-16'),
  ('커피 원두 정기배송', '먹거리',   17000,  '2026-10-12'),
  ('문서 작성 도구',     '업무',      8900,  '2026-10-22');

commit;
