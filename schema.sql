-- ==============================================================================
-- Franchise Scorecard & Multi-Tenant Operations Dashboard Schema
-- Database: Supabase / PostgreSQL (https://amjzomlovbuwjneqnumv.supabase.co)
-- ==============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 1. Locations Table (Franchise & Corporate Benchmark Stores)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_number INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT,
    region TEXT NOT NULL CHECK (region IN ('EAST', 'WEST')),
    store_type TEXT NOT NULL DEFAULT 'franchise' CHECK (store_type IN ('franchise', 'corporate')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookup by store number
CREATE INDEX IF NOT EXISTS idx_locations_store_number ON public.locations(store_number);
CREATE INDEX IF NOT EXISTS idx_locations_region ON public.locations(region);

-- ==============================================================================
-- 2. User Profiles Table (RBAC for Franchise Platform)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'store_manager' CHECK (role IN ('super_admin', 'admin', 'store_manager', 'accountant', 'staff')),
    organization_name TEXT,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON public.user_profiles(role);

-- ==============================================================================
-- 3. User Location Access Table (Many-to-Many Store Mapping)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.user_location_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES public.locations(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, location_id)
);

CREATE INDEX IF NOT EXISTS idx_user_location_access_user ON public.user_location_access(user_id);
CREATE INDEX IF NOT EXISTS idx_user_location_access_loc ON public.user_location_access(location_id);

-- ==============================================================================
-- 4. Scorecard Periods Table (MTD and Historical Monthly Snapshots)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.scorecard_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label TEXT UNIQUE NOT NULL, -- e.g. "Jan 2026 MTD", "Dec 2025", "Nov 25"
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    period_type TEXT NOT NULL CHECK (period_type IN ('MTD', 'FULL_MONTH')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 5. Monthly KPIs Table (Normalized Core Metrics + JSONB Overflow)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.monthly_kpis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.locations(id) ON DELETE CASCADE,
    period_id UUID NOT NULL REFERENCES public.scorecard_periods(id) ON DELETE CASCADE,
    
    -- Financials & Volume
    gross_revenue_actual NUMERIC DEFAULT 0,
    gross_revenue_projected NUMERIC DEFAULT 0,
    gross_revenue_mom_delta NUMERIC,
    gross_revenue_yoy_delta NUMERIC,
    sales_volume INTEGER DEFAULT 0,
    asp NUMERIC DEFAULT 0,
    daily_avg_revenue NUMERIC DEFAULT 0,

    -- Carrier Activations (Telus & Koodo)
    activations_total INTEGER DEFAULT 0,
    activations_new INTEGER DEFAULT 0,
    activations_renewals INTEGER DEFAULT 0,
    activations_migrations INTEGER DEFAULT 0,
    activations_telus_post INTEGER DEFAULT 0,
    activations_koodo_post INTEGER DEFAULT 0,
    activations_koodo_pre INTEGER DEFAULT 0,
    koodo_finance INTEGER DEFAULT 0,
    telus_finance INTEGER DEFAULT 0,

    -- Hardware & CPO (Certified Pre-Owned)
    cpo_units_actual INTEGER DEFAULT 0,
    cpo_units_projected INTEGER DEFAULT 0,
    cpo_revenue_actual NUMERIC DEFAULT 0,
    cpo_attach_activations_count INTEGER DEFAULT 0,
    cpo_attach_activations_pct NUMERIC DEFAULT 0,
    cpo_avg_sale NUMERIC DEFAULT 0,
    trade_in_units INTEGER DEFAULT 0,

    -- Technical Services & Repairs
    repairs_oow_volume INTEGER DEFAULT 0,
    repairs_oow_revenue NUMERIC DEFAULT 0,
    repairs_oow_daily_avg NUMERIC DEFAULT 0,
    repair_attach_activations_count INTEGER DEFAULT 0,
    repair_attach_activations_pct NUMERIC DEFAULT 0,
    repairs_insurance_volume INTEGER DEFAULT 0,
    repairs_insurance_revenue NUMERIC DEFAULT 0,

    -- Retail, Accessories & Protection
    accessories_volume INTEGER DEFAULT 0,
    accessories_revenue NUMERIC DEFAULT 0,
    accessory_attach_oow_repair_pct NUMERIC DEFAULT 0,
    protection_bundles_volume INTEGER DEFAULT 0,

    -- Foot Traffic & Conversion
    foot_traffic_total INTEGER DEFAULT 0,
    foot_traffic_daily_avg NUMERIC DEFAULT 0,
    foot_traffic_7day_ma NUMERIC DEFAULT 0,
    tickets_opened_7day_ma NUMERIC DEFAULT 0,
    conversion_rate_pct NUMERIC DEFAULT 0,

    -- Flexible overflow for any dynamic/unmapped columns
    raw_extended_metrics JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, period_id)
);

CREATE INDEX IF NOT EXISTS idx_monthly_kpis_loc ON public.monthly_kpis(location_id);
CREATE INDEX IF NOT EXISTS idx_monthly_kpis_period ON public.monthly_kpis(period_id);

-- ==============================================================================
-- 6. Weekly KPIs Table (WoW Historical Time-Series)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.weekly_kpis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES public.locations(id) ON DELETE CASCADE,
    week_end_date DATE NOT NULL,
    metric_type TEXT NOT NULL CHECK (metric_type IN ('activation', 'cpo', 'repair', 'traffic')),
    value NUMERIC NOT NULL DEFAULT 0,
    wow_delta NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, week_end_date, metric_type)
);

CREATE INDEX IF NOT EXISTS idx_weekly_kpis_loc_metric ON public.weekly_kpis(location_id, metric_type, week_end_date);

-- ==============================================================================
-- 7. Automated User Profile Trigger
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_scorecard_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, full_name, role)
    VALUES (
        new.id,
        new.email,
        COALESCE(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
        COALESCE(new.raw_user_meta_data->>'role', 'store_manager')
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE PROCEDURE public.handle_new_scorecard_user();

-- ==============================================================================
-- 8. Seed Locations (28 Franchise Stores + 12 Corporate Benchmark Stores)
-- ==============================================================================
INSERT INTO public.locations (store_number, name, short_name, region, store_type) VALUES
-- Franchise Stores (28)
(225, 'Mobile Klinik Brossard DIX30', 'Brossard DIX30', 'EAST', 'franchise'),
(930, 'Mobile Klinik Charlottetown', 'Charlottetown', 'EAST', 'franchise'),
(333, 'Mobile Klinik Country Hills', 'Country Hills', 'WEST', 'franchise'),
(170, 'Mobile Klinik Crossroads Milton', 'Crossroads Milton', 'EAST', 'franchise'),
(329, 'Mobile Klinik Edmonton Tamarack', 'Edmonton Tamarack', 'WEST', 'franchise'),
(175, 'Mobile Klinik Etobicoke Creek', 'Etobicoke Creek', 'EAST', 'franchise'),
(334, 'Mobile Klinik Griesbach', 'Griesbach', 'WEST', 'franchise'),
(816, 'Mobile Klinik Harvey Ave Kelowna', 'Harvey Ave Kelowna', 'WEST', 'franchise'),
(192, 'Mobile Klinik Heritage Plaza Peterborough', 'Heritage Plaza Peterborough', 'EAST', 'franchise'),
(185, 'Mobile Klinik Kanata', 'Kanata', 'EAST', 'franchise'),
(173, 'Mobile Klinik Kingston West End', 'Kingston West End', 'EAST', 'franchise'),
(326, 'Mobile Klinik Lethbridge', 'Lethbridge', 'WEST', 'franchise'),
(186, 'Mobile Klinik Merivale', 'Merivale', 'EAST', 'franchise'),
(824, 'Mobile Klinik Mid Island Nanaimo', 'MId Island Nanaimo', 'WEST', 'franchise'),
(825, 'Mobile Klinik Pine Centre', 'Pine Centre', 'WEST', 'franchise'),
(187, 'Mobile Klinik Progress Avenue', 'Progress Avenue', 'EAST', 'franchise'),
(174, 'Mobile Klinik Queens Downtown', 'Queens Downtown', 'EAST', 'franchise'),
(702, 'Mobile Klinik Regina East', 'Regina East', 'WEST', 'franchise'),
(703, 'Mobile Klinik Regina North', 'Regina North', 'WEST', 'franchise'),
(224, 'Mobile Klinik Saint Jean sur Richelieu', 'Saint Jean sur Richelieu', 'EAST', 'franchise'),
(336, 'Mobile Klinik Sherwood Park', 'Sherwood Park', 'WEST', 'franchise'),
(335, 'Mobile Klinik St Albert', 'St Albert', 'WEST', 'franchise'),
(704, 'Mobile Klinik Stonebridge', 'Stonebridge', 'WEST', 'franchise'),
(177, 'Mobile Klinik Taunton Road Oshawa', 'Taunton Road Oshawa', 'EAST', 'franchise'),
(328, 'Mobile Klinik Terra Losa', 'Terra Losa', 'WEST', 'franchise'),
(178, 'Mobile Klinik Whitby', 'Whitby', 'EAST', 'franchise'),
(182, 'Mobile Klinik Woodbridge', 'Woodbridge', 'WEST', 'franchise'),
(179, 'Mobile Klinik Yorkville', 'Yorkville', 'WEST', 'franchise'),

-- Corporate Benchmark Stores (12)
(160, 'Mobile Klinik Avenue Road', 'Avenue Road', 'EAST', 'corporate'),
(189, 'Mobile Klinik Barrhaven', 'Barrhaven', 'EAST', 'corporate'),
(901, 'Mobile Klinik Bedford', 'Bedford', 'EAST', 'corporate'),
(162, 'Mobile Klinik Danforth', 'Danforth', 'EAST', 'corporate'),
(161, 'Mobile Klinik Essa Road', 'Essa Road', 'EAST', 'corporate'),
(134, 'Mobile Klinik First Commerce', 'First Commerce', 'EAST', 'corporate'),
(114, 'Mobile Klinik Guelph', 'Guelph', 'EAST', 'corporate'),
(164, 'Mobile Klinik Hurontario', 'Hurontario', 'EAST', 'corporate'),
(109, 'Mobile Klinik Kitchener', 'Kitchener', 'EAST', 'corporate'),
(130, 'Mobile Klinik Park Place Barrie', 'Park Place Barrie', 'EAST', 'corporate'),
(190, 'Mobile Klinik Orleans', 'Orleans', 'EAST', 'corporate'),
(168, 'Mobile Klinik Thornhill', 'Thornhill', 'EAST', 'corporate')
ON CONFLICT (store_number) DO UPDATE SET 
    name = EXCLUDED.name,
    short_name = EXCLUDED.short_name,
    region = EXCLUDED.region,
    store_type = EXCLUDED.store_type;

-- ==============================================================================
-- 9. Row Level Security (RLS)
-- ==============================================================================
ALTER TABLE public.locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_location_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scorecard_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monthly_kpis ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weekly_kpis ENABLE ROW LEVEL SECURITY;

-- Note: The Python backend service role key bypasses RLS for batch ETL operations.
-- When client-side or user-scoped queries are made, policies restrict to assigned locations.
