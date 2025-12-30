--
-- PostgreSQL database dump
--

\restrict NoPkOa2glTqbIYR9zqqVHiUIaEgKYOe3yZd9SYVtziPMw7naHdb20eRHtfb3y2e

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bots; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.bots (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    display_name character varying(255),
    description text,
    exchange_id integer NOT NULL,
    workflow_id integer NOT NULL,
    is_active boolean DEFAULT true,
    trading_mode character varying(50) DEFAULT 'paper'::character varying,
    enable_tracing boolean DEFAULT true,
    tracing_project character varying(255) DEFAULT 'langtrader_pro'::character varying,
    max_concurrent_symbols integer DEFAULT 5,
    cycle_interval_seconds integer DEFAULT 180,
    max_position_size_percent numeric(5,2) DEFAULT 10.00,
    max_total_positions integer DEFAULT 5,
    max_leverage integer DEFAULT 1,
    initial_balance numeric(20,8),
    current_balance numeric(20,8),
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    last_active_at timestamp without time zone,
    created_by character varying(255),
    tracing_key character varying(255) DEFAULT 'None'::character varying NOT NULL,
    llm_id integer,
    prompt character varying(255) DEFAULT 'None'::character varying NOT NULL,
    quant_signal_weights jsonb DEFAULT '{"trend": 0.4, "volume": 0.2, "momentum": 0.3, "sentiment": 0.1}'::jsonb,
    quant_signal_threshold integer DEFAULT 50,
    risk_limits jsonb DEFAULT '{"max_single_symbol_pct": 0.3, "max_consecutive_losses": 5, "max_total_exposure_pct": 0.8}'::jsonb
);


ALTER TABLE public.bots OWNER TO tomiezhang;

--
-- Name: TABLE bots; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON TABLE public.bots IS '交易机器人配置中心';


--
-- Name: COLUMN bots.exchange_id; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.exchange_id IS '关联的交易所配置';


--
-- Name: COLUMN bots.workflow_id; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.workflow_id IS '使用的交易策略';


--
-- Name: COLUMN bots.enable_tracing; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.enable_tracing IS '是否启用 LangSmith 追踪';


--
-- Name: COLUMN bots.max_concurrent_symbols; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.max_concurrent_symbols IS '同时分析的最大币种数';


--
-- Name: COLUMN bots.tracing_key; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.tracing_key IS 'langsmith key';


--
-- Name: COLUMN bots.llm_id; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.llm_id IS '关联的 LLM 配置（NULL 则使用系统默认）';


--
-- Name: COLUMN bots.prompt; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.prompt IS '提示词模板名';


--
-- Name: COLUMN bots.quant_signal_weights; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.quant_signal_weights IS '量化信号权重配置 (趋势/动量/量能/情绪)';


--
-- Name: COLUMN bots.quant_signal_threshold; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.quant_signal_threshold IS '量化信号最低得分阈值 (0-100)';


--
-- Name: COLUMN bots.risk_limits; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.bots.risk_limits IS '动态风险管理阈值配置';


--
-- Name: bots_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.bots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.bots_id_seq OWNER TO tomiezhang;

--
-- Name: bots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.bots_id_seq OWNED BY public.bots.id;


--
-- Name: checkpoint_blobs; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.checkpoint_blobs (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    channel text NOT NULL,
    version text NOT NULL,
    type text NOT NULL,
    blob bytea
);


ALTER TABLE public.checkpoint_blobs OWNER TO tomiezhang;

--
-- Name: checkpoint_migrations; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.checkpoint_migrations (
    v integer NOT NULL
);


ALTER TABLE public.checkpoint_migrations OWNER TO tomiezhang;

--
-- Name: checkpoint_writes; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.checkpoint_writes (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    checkpoint_id text NOT NULL,
    task_id text NOT NULL,
    idx integer NOT NULL,
    channel text NOT NULL,
    type text,
    blob bytea NOT NULL,
    task_path text DEFAULT ''::text NOT NULL
);


ALTER TABLE public.checkpoint_writes OWNER TO tomiezhang;

--
-- Name: checkpoints; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.checkpoints (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    checkpoint_id text NOT NULL,
    parent_checkpoint_id text,
    type text,
    checkpoint jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE public.checkpoints OWNER TO tomiezhang;

--
-- Name: exchanges; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.exchanges (
    id integer NOT NULL,
    create_time date,
    name character varying(255),
    type character varying(255),
    apikey character varying(255),
    secretkey character varying(255),
    uid character varying(255),
    password character varying(255),
    createdat timestamp with time zone DEFAULT now() NOT NULL,
    updatedat timestamp with time zone DEFAULT now() NOT NULL,
    testnet boolean DEFAULT false NOT NULL,
    "IoTop" boolean DEFAULT false NOT NULL
);


ALTER TABLE public.exchanges OWNER TO tomiezhang;

--
-- Name: exchanges_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

ALTER TABLE public.exchanges ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.exchanges_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: llm_configs; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.llm_configs (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    display_name character varying(255),
    description text,
    provider character varying(100) DEFAULT 'openai'::character varying NOT NULL,
    model_name character varying(255) NOT NULL,
    base_url character varying(500),
    api_key text,
    temperature numeric(3,2) DEFAULT 0.7,
    max_retries integer DEFAULT 3,
    is_enabled boolean DEFAULT true,
    is_default boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by character varying(255)
);


ALTER TABLE public.llm_configs OWNER TO tomiezhang;

--
-- Name: TABLE llm_configs; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON TABLE public.llm_configs IS 'LLM 配置中心 - 统一管理所有 LLM 提供者和模型配置';


--
-- Name: COLUMN llm_configs.provider; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.llm_configs.provider IS 'LLM 提供者：openai, anthropic, azure, ollama, custom';


--
-- Name: COLUMN llm_configs.model_name; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.llm_configs.model_name IS '模型名称：gpt-4o-mini, claude-3-5-sonnet-20241022 等';


--
-- Name: COLUMN llm_configs.base_url; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.llm_configs.base_url IS '自定义 API 端点（可选，用于私有部署或代理）';


--
-- Name: COLUMN llm_configs.is_default; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.llm_configs.is_default IS '是否为系统默认 LLM（只能有一个）';


--
-- Name: llm_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.llm_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.llm_configs_id_seq OWNER TO tomiezhang;

--
-- Name: llm_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.llm_configs_id_seq OWNED BY public.llm_configs.id;


--
-- Name: node_configs; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.node_configs (
    id integer NOT NULL,
    node_id integer NOT NULL,
    config_key character varying(255) NOT NULL,
    config_value text NOT NULL,
    value_type character varying(50) DEFAULT 'string'::character varying,
    description text,
    is_secret boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.node_configs OWNER TO tomiezhang;

--
-- Name: node_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.node_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.node_configs_id_seq OWNER TO tomiezhang;

--
-- Name: node_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.node_configs_id_seq OWNED BY public.node_configs.id;


--
-- Name: trade_history; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.trade_history (
    id integer NOT NULL,
    bot_id integer NOT NULL,
    symbol character varying NOT NULL,
    side character varying NOT NULL,
    action character varying NOT NULL,
    entry_price numeric,
    exit_price numeric,
    amount numeric NOT NULL,
    leverage integer NOT NULL,
    pnl_usd numeric,
    pnl_percent numeric,
    fee_paid numeric,
    status character varying NOT NULL,
    opened_at timestamp without time zone NOT NULL,
    closed_at timestamp without time zone,
    cycle_id character varying,
    order_id character varying
);


ALTER TABLE public.trade_history OWNER TO tomiezhang;

--
-- Name: trade_history_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.trade_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.trade_history_id_seq OWNER TO tomiezhang;

--
-- Name: trade_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.trade_history_id_seq OWNED BY public.trade_history.id;


--
-- Name: workflow_audit_log; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.workflow_audit_log (
    id integer NOT NULL,
    workflow_id integer,
    action character varying(50),
    changed_by character varying(255),
    changed_at timestamp without time zone DEFAULT now(),
    before_value jsonb,
    after_value jsonb,
    change_summary text
);


ALTER TABLE public.workflow_audit_log OWNER TO tomiezhang;

--
-- Name: workflow_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.workflow_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflow_audit_log_id_seq OWNER TO tomiezhang;

--
-- Name: workflow_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.workflow_audit_log_id_seq OWNED BY public.workflow_audit_log.id;


--
-- Name: workflow_edges; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.workflow_edges (
    id integer NOT NULL,
    workflow_id integer NOT NULL,
    from_node character varying(255) NOT NULL,
    to_node character varying(255) NOT NULL,
    condition text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.workflow_edges OWNER TO tomiezhang;

--
-- Name: workflow_edges_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.workflow_edges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflow_edges_id_seq OWNER TO tomiezhang;

--
-- Name: workflow_edges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.workflow_edges_id_seq OWNED BY public.workflow_edges.id;


--
-- Name: workflow_executions; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.workflow_executions (
    id integer NOT NULL,
    workflow_id integer NOT NULL,
    bot_id integer,
    status character varying(50) DEFAULT 'running'::character varying,
    started_at timestamp without time zone DEFAULT now(),
    finished_at timestamp without time zone,
    symbols_count integer,
    decisions_count integer,
    executions_count integer,
    error_message text,
    duration_ms integer
);


ALTER TABLE public.workflow_executions OWNER TO tomiezhang;

--
-- Name: workflow_executions_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.workflow_executions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflow_executions_id_seq OWNER TO tomiezhang;

--
-- Name: workflow_executions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.workflow_executions_id_seq OWNED BY public.workflow_executions.id;


--
-- Name: workflow_nodes; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.workflow_nodes (
    id integer NOT NULL,
    workflow_id integer NOT NULL,
    name character varying(255) NOT NULL,
    plugin_name character varying(255) NOT NULL,
    enabled boolean DEFAULT true,
    execution_order integer DEFAULT 0,
    condition text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.workflow_nodes OWNER TO tomiezhang;

--
-- Name: workflow_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.workflow_nodes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflow_nodes_id_seq OWNER TO tomiezhang;

--
-- Name: workflow_nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.workflow_nodes_id_seq OWNED BY public.workflow_nodes.id;


--
-- Name: workflows; Type: TABLE; Schema: public; Owner: tomiezhang
--

CREATE TABLE public.workflows (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    display_name character varying(255),
    version character varying(50) DEFAULT '1.0.0'::character varying,
    description text,
    category character varying(50) DEFAULT 'trading'::character varying,
    tags text[],
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by character varying(255)
);


ALTER TABLE public.workflows OWNER TO tomiezhang;

--
-- Name: TABLE workflows; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON TABLE public.workflows IS 'Workflow 策略定义（可复用）';


--
-- Name: COLUMN workflows.category; Type: COMMENT; Schema: public; Owner: tomiezhang
--

COMMENT ON COLUMN public.workflows.category IS '策略类别';


--
-- Name: workflows_id_seq; Type: SEQUENCE; Schema: public; Owner: tomiezhang
--

CREATE SEQUENCE public.workflows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflows_id_seq OWNER TO tomiezhang;

--
-- Name: workflows_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: tomiezhang
--

ALTER SEQUENCE public.workflows_id_seq OWNED BY public.workflows.id;


--
-- Name: bots id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.bots ALTER COLUMN id SET DEFAULT nextval('public.bots_id_seq'::regclass);


--
-- Name: llm_configs id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.llm_configs ALTER COLUMN id SET DEFAULT nextval('public.llm_configs_id_seq'::regclass);


--
-- Name: node_configs id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.node_configs ALTER COLUMN id SET DEFAULT nextval('public.node_configs_id_seq'::regclass);


--
-- Name: trade_history id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.trade_history ALTER COLUMN id SET DEFAULT nextval('public.trade_history_id_seq'::regclass);


--
-- Name: workflow_audit_log id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_audit_log ALTER COLUMN id SET DEFAULT nextval('public.workflow_audit_log_id_seq'::regclass);


--
-- Name: workflow_edges id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_edges ALTER COLUMN id SET DEFAULT nextval('public.workflow_edges_id_seq'::regclass);


--
-- Name: workflow_executions id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_executions ALTER COLUMN id SET DEFAULT nextval('public.workflow_executions_id_seq'::regclass);


--
-- Name: workflow_nodes id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_nodes ALTER COLUMN id SET DEFAULT nextval('public.workflow_nodes_id_seq'::regclass);


--
-- Name: workflows id; Type: DEFAULT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflows ALTER COLUMN id SET DEFAULT nextval('public.workflows_id_seq'::regclass);


--
-- Name: bots bots_name_key; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.bots
    ADD CONSTRAINT bots_name_key UNIQUE (name);


--
-- Name: bots bots_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.bots
    ADD CONSTRAINT bots_pkey PRIMARY KEY (id);


--
-- Name: checkpoint_blobs checkpoint_blobs_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.checkpoint_blobs
    ADD CONSTRAINT checkpoint_blobs_pkey PRIMARY KEY (thread_id, checkpoint_ns, channel, version);


--
-- Name: checkpoint_migrations checkpoint_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.checkpoint_migrations
    ADD CONSTRAINT checkpoint_migrations_pkey PRIMARY KEY (v);


--
-- Name: checkpoint_writes checkpoint_writes_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.checkpoint_writes
    ADD CONSTRAINT checkpoint_writes_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx);


--
-- Name: checkpoints checkpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.checkpoints
    ADD CONSTRAINT checkpoints_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id);


--
-- Name: exchanges exchanges_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.exchanges
    ADD CONSTRAINT exchanges_pkey PRIMARY KEY (id);


--
-- Name: llm_configs llm_configs_name_key; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.llm_configs
    ADD CONSTRAINT llm_configs_name_key UNIQUE (name);


--
-- Name: llm_configs llm_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.llm_configs
    ADD CONSTRAINT llm_configs_pkey PRIMARY KEY (id);


--
-- Name: node_configs node_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.node_configs
    ADD CONSTRAINT node_configs_pkey PRIMARY KEY (id);


--
-- Name: trade_history trade_history_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.trade_history
    ADD CONSTRAINT trade_history_pkey PRIMARY KEY (id);


--
-- Name: node_configs unique_config_per_node; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.node_configs
    ADD CONSTRAINT unique_config_per_node UNIQUE (node_id, config_key);


--
-- Name: workflow_edges unique_edge_per_workflow; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT unique_edge_per_workflow UNIQUE (workflow_id, from_node, to_node);


--
-- Name: workflow_nodes unique_node_name_per_workflow; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_nodes
    ADD CONSTRAINT unique_node_name_per_workflow UNIQUE (workflow_id, name);


--
-- Name: workflow_audit_log workflow_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_audit_log
    ADD CONSTRAINT workflow_audit_log_pkey PRIMARY KEY (id);


--
-- Name: workflow_edges workflow_edges_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_edges
    ADD CONSTRAINT workflow_edges_pkey PRIMARY KEY (id);


--
-- Name: workflow_executions workflow_executions_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_executions
    ADD CONSTRAINT workflow_executions_pkey PRIMARY KEY (id);


--
-- Name: workflow_nodes workflow_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflow_nodes
    ADD CONSTRAINT workflow_nodes_pkey PRIMARY KEY (id);


--
-- Name: workflows workflows_name_key; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_name_key UNIQUE (name);


--
-- Name: workflows workflows_pkey; Type: CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_pkey PRIMARY KEY (id);


--
-- Name: checkpoint_blobs_thread_id_idx; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX checkpoint_blobs_thread_id_idx ON public.checkpoint_blobs USING btree (thread_id);


--
-- Name: checkpoint_writes_thread_id_idx; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX checkpoint_writes_thread_id_idx ON public.checkpoint_writes USING btree (thread_id);


--
-- Name: checkpoints_thread_id_idx; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX checkpoints_thread_id_idx ON public.checkpoints USING btree (thread_id);


--
-- Name: idx_audit_log_time; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_audit_log_time ON public.workflow_audit_log USING btree (changed_at);


--
-- Name: idx_audit_log_workflow; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_audit_log_workflow ON public.workflow_audit_log USING btree (workflow_id);


--
-- Name: idx_bots_active; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_bots_active ON public.bots USING btree (is_active);


--
-- Name: idx_bots_exchange; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_bots_exchange ON public.bots USING btree (exchange_id);


--
-- Name: idx_bots_llm; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_bots_llm ON public.bots USING btree (llm_id);


--
-- Name: idx_bots_quant_config; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_bots_quant_config ON public.bots USING gin (quant_signal_weights);


--
-- Name: idx_bots_risk_config; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_bots_risk_config ON public.bots USING gin (risk_limits);


--
-- Name: idx_bots_trading_mode; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_bots_trading_mode ON public.bots USING btree (trading_mode);


--
-- Name: idx_bots_workflow; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_bots_workflow ON public.bots USING btree (workflow_id);


--
-- Name: idx_llm_configs_default; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_llm_configs_default ON public.llm_configs USING btree (is_default);


--
-- Name: idx_llm_configs_enabled; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_llm_configs_enabled ON public.llm_configs USING btree (is_enabled);


--
-- Name: idx_llm_configs_provider; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_llm_configs_provider ON public.llm_configs USING btree (provider);


--
-- Name: idx_node_configs_node; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_node_configs_node ON public.node_configs USING btree (node_id);


--
-- Name: idx_workflow_edges_workflow; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflow_edges_workflow ON public.workflow_edges USING btree (workflow_id);


--
-- Name: idx_workflow_executions_bot; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflow_executions_bot ON public.workflow_executions USING btree (bot_id);


--
-- Name: idx_workflow_executions_status; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflow_executions_status ON public.workflow_executions USING btree (status, started_at);


--
-- Name: idx_workflow_executions_workflow; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflow_executions_workflow ON public.workflow_executions USING btree (workflow_id);


--
-- Name: idx_workflow_nodes_order; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflow_nodes_order ON public.workflow_nodes USING btree (workflow_id, execution_order);


--
-- Name: idx_workflow_nodes_workflow; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflow_nodes_workflow ON public.workflow_nodes USING btree (workflow_id);


--
-- Name: idx_workflows_category; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflows_category ON public.workflows USING btree (category);


--
-- Name: idx_workflows_name; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX idx_workflows_name ON public.workflows USING btree (name);


--
-- Name: ix_trade_history_bot_id; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX ix_trade_history_bot_id ON public.trade_history USING btree (bot_id);


--
-- Name: ix_trade_history_symbol; Type: INDEX; Schema: public; Owner: tomiezhang
--

CREATE INDEX ix_trade_history_symbol ON public.trade_history USING btree (symbol);


--
-- Name: bots bots_exchange_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.bots
    ADD CONSTRAINT bots_exchange_id_fkey FOREIGN KEY (exchange_id) REFERENCES public.exchanges(id) ON DELETE RESTRICT;


--
-- Name: bots bots_llm_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.bots
    ADD CONSTRAINT bots_llm_id_fkey FOREIGN KEY (llm_id) REFERENCES public.llm_configs(id) ON DELETE SET NULL;


--
-- Name: node_configs node_configs_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.node_configs
    ADD CONSTRAINT node_configs_node_id_fkey FOREIGN KEY (node_id) REFERENCES public.workflow_nodes(id) ON DELETE CASCADE;


--
-- Name: trade_history trade_history_bot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: tomiezhang
--

ALTER TABLE ONLY public.trade_history
    ADD CONSTRAINT trade_history_bot_id_fkey FOREIGN KEY (bot_id) REFERENCES public.bots(id);


--
-- PostgreSQL database dump complete
--

\unrestrict NoPkOa2glTqbIYR9zqqVHiUIaEgKYOe3yZd9SYVtziPMw7naHdb20eRHtfb3y2e

