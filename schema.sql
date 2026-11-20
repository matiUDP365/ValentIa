-- Ejecutar en SQL Editor del proyecto Supabase.
begin;
create table if not exists public.telemetry_packets (
    id uuid primary key default gen_random_uuid(),
    device_id text not null check (length(device_id) between 1 and 64),
    source text not null check (source in ('raspberry', 'simulation')),
    received_at timestamptz not null default now(),
    components jsonb not null check (jsonb_typeof(components) = 'array' and jsonb_array_length(components) between 1 and 3)
);
create index if not exists telemetry_received_idx on public.telemetry_packets(received_at desc, id desc);
create table if not exists public.sign_samples (
    id uuid primary key default gen_random_uuid(),
    label text not null check (length(label) between 1 and 64),
    prediction text,
    confidence double precision check (confidence between 0 and 1),
    handedness text not null check (handedness in ('Left', 'Right', 'Both', 'unknown')),
    landmarks jsonb not null check (jsonb_typeof(landmarks) = 'array' and jsonb_array_length(landmarks) in (0, 21, 42)),
    features jsonb not null check (jsonb_typeof(features) = 'array' and jsonb_array_length(features) in (63, 126)),
    captured_at timestamptz not null,
    created_at timestamptz not null default now()
);
-- Permite ejecutar este esquema sobre la versión previa de muestras de una mano.
alter table public.sign_samples drop constraint if exists sign_samples_handedness_check;
alter table public.sign_samples add constraint sign_samples_handedness_check
    check (handedness in ('Left', 'Right', 'Both', 'unknown'));
alter table public.sign_samples drop constraint if exists sign_samples_landmarks_check;
alter table public.sign_samples add constraint sign_samples_landmarks_check
    check (jsonb_typeof(landmarks) = 'array' and jsonb_array_length(landmarks) in (0, 21, 42));
alter table public.sign_samples drop constraint if exists sign_samples_features_check;
alter table public.sign_samples add constraint sign_samples_features_check
    check (jsonb_typeof(features) = 'array' and jsonb_array_length(features) in (63, 126));
create index if not exists signs_captured_idx on public.sign_samples(captured_at desc, id desc);
alter table public.telemetry_packets enable row level security;
alter table public.sign_samples enable row level security;
-- Solo Flask con la clave secreta tiene acceso. Sin políticas públicas.
revoke all on public.telemetry_packets, public.sign_samples from anon, authenticated;
grant select, insert on public.telemetry_packets, public.sign_samples to service_role;
commit;
