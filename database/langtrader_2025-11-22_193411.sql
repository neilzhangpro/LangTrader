--
-- PostgreSQL database dump
--

\restrict gHXek6JWmB03pgS7W2Hsbu0R2ouwpaIarilhL2zwtSUlAXSd7eMMNAzPLq1talo

-- Dumped from database version 14.19 (Homebrew)
-- Dumped by pg_dump version 14.19 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: auto_calculate_position_pnl(); Type: FUNCTION; Schema: public; Owner: tomiezhang
--

CREATE FUNCTION public.auto_calculate_position_pnl() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- 当有 exit_price 时自动计算 PnL
    IF NEW.exit_price IS NOT NULL THEN
        NEW.realized_pnl = calc_pnl(
            NEW.side,
            NEW.entry_price,
            NEW.exit_price,
            NEW.quantity,
            NEW.leverage
        );
        
        -- 自动设置 closed_at
        IF NEW.status = 'closed' AND NEW.closed_at IS NULL THEN
            NEW.closed_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.auto_calculate_position_pnl() OWNER TO tomiezhang;

--
-- Name: calc_pnl(character varying, numeric, numeric, numeric, integer); Type: FUNCTION; Schema: public; Owner: tomiezhang
--

CREATE FUNCTION public.calc_pnl(p_side character varying, p_entry_price numeric, p_exit_price numeric, p_quantity numeric, p_leverage integer) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF p_side = 'LONG' THEN
        RETURN (p_exit_price - p_entry_price) * p_quantity * p_leverage;
    ELSE
        RETURN (p_entry_price - p_exit_price) * p_quantity * p_leverage;
    END IF;
END;
$$;


ALTER FUNCTION public.calc_pnl(p_side character varying, p_entry_price numeric, p_exit_price numeric, p_quantity numeric, p_leverage integer) OWNER TO tomiezhang;

--
-- Name: update_updated_at(); Type: FUNCTION; Schema: public; Owner: tomiezhang
--

CREATE FUNCTION public.update_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at() OWNER TO tomiezhang;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_competitions; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.ai_competitions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trader_id uuid NOT NULL,
    competition_time timestamp without time zone DEFAULT now(),
    models_competed jsonb NOT NULL,
    winner_model character varying(50) NOT NULL,
    winner_confidence numeric(5,4) NOT NULL,
    winner_decision jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.ai_competitions OWNER TO tomiezhang;

--
-- Name: ai_model_performance; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.ai_model_performance (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trader_id uuid NOT NULL,
    model_name character varying(50) NOT NULL,
    total_competitions integer DEFAULT 0,
    times_selected integer DEFAULT 0,
    selection_rate numeric(5,2) DEFAULT 0.00,
    total_trades integer DEFAULT 0,
    winning_trades integer DEFAULT 0,
    losing_trades integer DEFAULT 0,
    win_rate numeric(5,2) DEFAULT 0.00,
    total_pnl numeric(15,2) DEFAULT 0.00,
    avg_confidence numeric(5,4) DEFAULT 0.00,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.ai_model_performance OWNER TO tomiezhang;

--
-- Name: coin_performance_analysis; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.coin_performance_analysis (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trader_id uuid NOT NULL,
    symbol character varying(20) NOT NULL,
    total_trades integer DEFAULT 0,
    winning_trades integer DEFAULT 0,
    losing_trades integer DEFAULT 0,
    win_rate numeric(5,2) DEFAULT 0.00,
    avg_profit_pct numeric(10,4) DEFAULT 0.00,
    avg_loss_pct numeric(10,4) DEFAULT 0.00,
    consecutive_wins integer DEFAULT 0,
    consecutive_losses integer DEFAULT 0,
    total_pnl numeric(15,2) DEFAULT 0.00,
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.coin_performance_analysis OWNER TO tomiezhang;

--
-- Name: decisions; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.decisions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trader_id uuid NOT NULL,
    symbol character varying(20) NOT NULL,
    market_data jsonb NOT NULL,
    indicators jsonb NOT NULL,
    llm_analysis jsonb NOT NULL,
    action character varying(10) NOT NULL,
    confidence double precision,
    risk_passed boolean DEFAULT false NOT NULL,
    executed boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    competition_id uuid,
    winner_model character varying(50),
    CONSTRAINT decisions_confidence_check CHECK (((confidence >= (0)::double precision) AND (confidence <= (1)::double precision)))
);


ALTER TABLE public.decisions OWNER TO tomiezhang;

--
-- Name: equity_history; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.equity_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trader_id uuid NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now() NOT NULL,
    equity numeric(18,8) NOT NULL,
    withdrawable numeric(18,8),
    margin_used numeric(18,8),
    open_positions integer DEFAULT 0,
    total_position_value numeric(18,8),
    unrealized_pnl numeric(18,8),
    realized_pnl_total numeric(18,8),
    decision_id uuid,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.equity_history OWNER TO tomiezhang;

--
-- Name: performance_cache; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.performance_cache (
    trader_id uuid NOT NULL,
    total_trades integer,
    win_rate numeric(5,4),
    total_pnl numeric(18,8),
    sharpe_ratio numeric(10,4),
    max_drawdown numeric(10,4),
    current_drawdown numeric(10,4),
    performance_status character varying(20),
    risk_level character varying(20),
    last_updated timestamp without time zone DEFAULT now()
);


ALTER TABLE public.performance_cache OWNER TO tomiezhang;

--
-- Name: positions; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.positions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trader_id uuid NOT NULL,
    decision_id uuid,
    symbol character varying(20) NOT NULL,
    side character varying(10) NOT NULL,
    entry_price numeric(18,8) NOT NULL,
    quantity numeric(18,8) NOT NULL,
    leverage integer DEFAULT 1 NOT NULL,
    exit_price numeric(18,8),
    exit_reason character varying(50),
    stop_loss numeric(18,8),
    take_profit numeric(18,8),
    realized_pnl numeric(18,8),
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    opened_at timestamp without time zone DEFAULT now() NOT NULL,
    closed_at timestamp without time zone,
    competition_id uuid
);


ALTER TABLE public.positions OWNER TO tomiezhang;

--
-- Name: traders; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.traders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    exchange character varying(50) NOT NULL,
    symbols jsonb NOT NULL,
    llm_config jsonb NOT NULL,
    risk_config jsonb NOT NULL,
    system_prompt text NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    exchange_configs jsonb DEFAULT '{}'::jsonb NOT NULL,
    custom_system_prompt text,
    custom_user_prompt text
);


ALTER TABLE public.traders OWNER TO tomiezhang;

--
-- Name: COLUMN traders.custom_system_prompt; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.traders.custom_system_prompt IS '自定义系统提示词（AI角色定义），如果设置则完全替换默认system_prompt';


--
-- Name: COLUMN traders.custom_user_prompt; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.traders.custom_user_prompt IS '自定义用户提示词模板（支持变量占位符），如果设置则完全替换默认user_prompt生成逻辑';


--
-- Name: v_trader_stats; Type: VIEW; Schema: public; Owner: tomiezhang
--

CREATE VIEW public.v_trader_stats AS
 SELECT t.id,
    t.name,
    t.status,
    count(DISTINCT d.id) AS total_decisions,
    count(DISTINCT
        CASE
            WHEN d.executed THEN d.id
            ELSE NULL::uuid
        END) AS executed_count,
    count(DISTINCT p.id) AS total_trades,
    count(DISTINCT
        CASE
            WHEN ((p.status)::text = 'open'::text) THEN p.id
            ELSE NULL::uuid
        END) AS open_positions,
    count(DISTINCT
        CASE
            WHEN (p.realized_pnl > (0)::numeric) THEN p.id
            ELSE NULL::uuid
        END) AS winning_trades,
    count(DISTINCT
        CASE
            WHEN (p.realized_pnl < (0)::numeric) THEN p.id
            ELSE NULL::uuid
        END) AS losing_trades,
    COALESCE(sum(p.realized_pnl), (0)::numeric) AS total_pnl,
        CASE
            WHEN (count(DISTINCT
            CASE
                WHEN ((p.status)::text = 'closed'::text) THEN p.id
                ELSE NULL::uuid
            END) > 0) THEN round(((count(DISTINCT
            CASE
                WHEN (p.realized_pnl > (0)::numeric) THEN p.id
                ELSE NULL::uuid
            END))::numeric / (count(DISTINCT
            CASE
                WHEN ((p.status)::text = 'closed'::text) THEN p.id
                ELSE NULL::uuid
            END))::numeric), 4)
            ELSE (0)::numeric
        END AS win_rate
   FROM ((public.traders t
     LEFT JOIN public.decisions d ON ((t.id = d.trader_id)))
     LEFT JOIN public.positions p ON ((t.id = p.trader_id)))
  GROUP BY t.id, t.name, t.status;


ALTER TABLE public.v_trader_stats OWNER TO tomiezhang;

--
-- Name: ai_competitions ai_competitions_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.ai_competitions
    ADD CONSTRAINT ai_competitions_pkey PRIMARY KEY (id);


--
-- Name: ai_model_performance ai_model_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.ai_model_performance
    ADD CONSTRAINT ai_model_performance_pkey PRIMARY KEY (id);


--
-- Name: ai_model_performance ai_model_performance_trader_id_model_name_key; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.ai_model_performance
    ADD CONSTRAINT ai_model_performance_trader_id_model_name_key UNIQUE (trader_id, model_name);


--
-- Name: coin_performance_analysis coin_performance_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.coin_performance_analysis
    ADD CONSTRAINT coin_performance_analysis_pkey PRIMARY KEY (id);


--
-- Name: coin_performance_analysis coin_performance_analysis_trader_id_symbol_key; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.coin_performance_analysis
    ADD CONSTRAINT coin_performance_analysis_trader_id_symbol_key UNIQUE (trader_id, symbol);


--
-- Name: decisions decisions_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.decisions
    ADD CONSTRAINT decisions_pkey PRIMARY KEY (id);


--
-- Name: equity_history equity_history_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.equity_history
    ADD CONSTRAINT equity_history_pkey PRIMARY KEY (id);


--
-- Name: performance_cache performance_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.performance_cache
    ADD CONSTRAINT performance_cache_pkey PRIMARY KEY (trader_id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: traders traders_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.traders
    ADD CONSTRAINT traders_pkey PRIMARY KEY (id);


--
-- Name: idx_coin_perf_trader; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_coin_perf_trader ON public.coin_performance_analysis USING btree (trader_id);


--
-- Name: idx_competitions_trader; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_competitions_trader ON public.ai_competitions USING btree (trader_id);


--
-- Name: idx_decisions_executed; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_decisions_executed ON public.decisions USING btree (executed);


--
-- Name: idx_decisions_trader_time; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_decisions_trader_time ON public.decisions USING btree (trader_id, created_at DESC);


--
-- Name: idx_equity_trader_time; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_equity_trader_time ON public.equity_history USING btree (trader_id, "timestamp" DESC);


--
-- Name: idx_model_perf_trader; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_model_perf_trader ON public.ai_model_performance USING btree (trader_id);


--
-- Name: idx_positions_opened_at; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_positions_opened_at ON public.positions USING btree (opened_at DESC);


--
-- Name: idx_positions_trader_status; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_positions_trader_status ON public.positions USING btree (trader_id, status);


--
-- Name: positions trg_auto_calculate_pnl; Type: TRIGGER; Schema: public; Owner: tomiezhang
--

CREATE TRIGGER trg_auto_calculate_pnl BEFORE INSERT OR UPDATE ON public.positions FOR EACH ROW EXECUTE FUNCTION public.auto_calculate_position_pnl();


--
-- Name: traders trg_traders_updated_at; Type: TRIGGER; Schema: public; Owner: tomiezhang
--

CREATE TRIGGER trg_traders_updated_at BEFORE UPDATE ON public.traders FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();


--
-- Name: decisions decisions_competition_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.decisions
    ADD CONSTRAINT decisions_competition_id_fkey FOREIGN KEY (competition_id) REFERENCES public.ai_competitions(id);


--
-- Name: decisions decisions_trader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.decisions
    ADD CONSTRAINT decisions_trader_id_fkey FOREIGN KEY (trader_id) REFERENCES public.traders(id) ON DELETE CASCADE;


--
-- Name: equity_history equity_history_decision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.equity_history
    ADD CONSTRAINT equity_history_decision_id_fkey FOREIGN KEY (decision_id) REFERENCES public.decisions(id);


--
-- Name: equity_history equity_history_trader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.equity_history
    ADD CONSTRAINT equity_history_trader_id_fkey FOREIGN KEY (trader_id) REFERENCES public.traders(id);


--
-- Name: performance_cache performance_cache_trader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.performance_cache
    ADD CONSTRAINT performance_cache_trader_id_fkey FOREIGN KEY (trader_id) REFERENCES public.traders(id);


--
-- Name: positions positions_competition_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_competition_id_fkey FOREIGN KEY (competition_id) REFERENCES public.ai_competitions(id);


--
-- Name: positions positions_decision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_decision_id_fkey FOREIGN KEY (decision_id) REFERENCES public.decisions(id);


--
-- Name: positions positions_trader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_trader_id_fkey FOREIGN KEY (trader_id) REFERENCES public.traders(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict gHXek6JWmB03pgS7W2Hsbu0R2ouwpaIarilhL2zwtSUlAXSd7eMMNAzPLq1talo

