--
-- PostgreSQL database dump
--

\restrict 71NCjuelAfZui68LalcMo0XWb71vpT3OGR2x9iUl4cB27vK2P9bcmeCt4E4CATh

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
    CONSTRAINT decisions_confidence_check CHECK (((confidence >= (0)::double precision) AND (confidence <= (1)::double precision)))
);


ALTER TABLE public.decisions OWNER TO tomiezhang;

--
-- Name: learning_logs; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.learning_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trader_id uuid NOT NULL,
    input_summary jsonb NOT NULL,
    insights text NOT NULL,
    strategy_updates jsonb,
    old_prompt text,
    new_prompt text,
    applied boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.learning_logs OWNER TO tomiezhang;

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
    closed_at timestamp without time zone
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
    exchange_configs jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE public.traders OWNER TO tomiezhang;

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
-- Name: decisions decisions_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.decisions
    ADD CONSTRAINT decisions_pkey PRIMARY KEY (id);


--
-- Name: learning_logs learning_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.learning_logs
    ADD CONSTRAINT learning_logs_pkey PRIMARY KEY (id);


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
-- Name: idx_decisions_executed; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_decisions_executed ON public.decisions USING btree (executed);


--
-- Name: idx_decisions_trader_time; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_decisions_trader_time ON public.decisions USING btree (trader_id, created_at DESC);


--
-- Name: idx_learning_logs_trader_time; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_learning_logs_trader_time ON public.learning_logs USING btree (trader_id, created_at DESC);


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
-- Name: decisions decisions_trader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.decisions
    ADD CONSTRAINT decisions_trader_id_fkey FOREIGN KEY (trader_id) REFERENCES public.traders(id) ON DELETE CASCADE;


--
-- Name: learning_logs learning_logs_trader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.learning_logs
    ADD CONSTRAINT learning_logs_trader_id_fkey FOREIGN KEY (trader_id) REFERENCES public.traders(id) ON DELETE CASCADE;


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

\unrestrict 71NCjuelAfZui68LalcMo0XWb71vpT3OGR2x9iUl4cB27vK2P9bcmeCt4E4CATh

