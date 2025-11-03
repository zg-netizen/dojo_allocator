--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13
-- Dumped by pg_dump version 15.13

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
-- Name: timescaledb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;


--
-- Name: EXTENSION timescaledb; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION timescaledb IS 'Enables scalable inserts and complex queries for time-series data (Community Edition)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: dojo
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT now() NOT NULL,
    event_type character varying(50) NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id character varying(64) NOT NULL,
    actor character varying(50) NOT NULL,
    action character varying(255) NOT NULL,
    before_state json,
    after_state json,
    event_hash character varying(64) NOT NULL,
    previous_hash character varying(64)
);


ALTER TABLE public.audit_log OWNER TO dojo;

--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: dojo
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.audit_log_id_seq OWNER TO dojo;

--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: dojo
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: dojo
--

CREATE TABLE public.orders (
    id integer NOT NULL,
    order_id character varying(64) NOT NULL,
    broker_order_id character varying(64),
    position_id character varying(64),
    symbol character varying(10) NOT NULL,
    side character varying(4) NOT NULL,
    order_type character varying(20) NOT NULL,
    quantity numeric NOT NULL,
    limit_price numeric,
    stop_price numeric,
    status character varying(20) NOT NULL,
    filled_qty numeric,
    filled_avg_price numeric,
    commission numeric,
    submitted_at timestamp without time zone,
    filled_at timestamp without time zone,
    error_message text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.orders OWNER TO dojo;

--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: dojo
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.orders_id_seq OWNER TO dojo;

--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: dojo
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: philosophy_state; Type: TABLE; Schema: public; Owner: dojo
--

CREATE TABLE public.philosophy_state (
    id integer NOT NULL,
    date date NOT NULL,
    decisions_logged integer,
    intuition_overrides integer,
    trades_with_safety numeric,
    trades_without_safety numeric,
    cluster_signals_detected integer,
    cluster_positions_taken integer,
    positions_retired integer,
    avg_return_per_cycle numeric,
    positions_extended integer,
    avg_sharpe_at_extension numeric,
    rule_violations integer,
    violated_rules json,
    current_allocation_power numeric,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.philosophy_state OWNER TO dojo;

--
-- Name: philosophy_state_id_seq; Type: SEQUENCE; Schema: public; Owner: dojo
--

CREATE SEQUENCE public.philosophy_state_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.philosophy_state_id_seq OWNER TO dojo;

--
-- Name: philosophy_state_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: dojo
--

ALTER SEQUENCE public.philosophy_state_id_seq OWNED BY public.philosophy_state.id;


--
-- Name: positions; Type: TABLE; Schema: public; Owner: dojo
--

CREATE TABLE public.positions (
    id integer NOT NULL,
    position_id character varying(64) NOT NULL,
    symbol character varying(10) NOT NULL,
    direction character varying(4) NOT NULL,
    entry_date timestamp without time zone NOT NULL,
    entry_price numeric,
    shares numeric NOT NULL,
    entry_value numeric,
    source_signals character varying[],
    conviction_tier character varying(10),
    philosophy_applied character varying(50),
    exit_date timestamp without time zone,
    exit_price numeric,
    exit_value numeric,
    realized_pnl numeric,
    return_pct numeric,
    round_start timestamp without time zone NOT NULL,
    round_expiry timestamp without time zone NOT NULL,
    round_extended boolean,
    discipline_violations integer,
    status character varying(20),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.positions OWNER TO dojo;

--
-- Name: positions_id_seq; Type: SEQUENCE; Schema: public; Owner: dojo
--

CREATE SEQUENCE public.positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.positions_id_seq OWNER TO dojo;

--
-- Name: positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: dojo
--

ALTER SEQUENCE public.positions_id_seq OWNED BY public.positions.id;


--
-- Name: signals; Type: TABLE; Schema: public; Owner: dojo
--

CREATE TABLE public.signals (
    id integer NOT NULL,
    signal_id character varying(64) NOT NULL,
    source character varying(32) NOT NULL,
    symbol character varying(10) NOT NULL,
    direction character varying(4) NOT NULL,
    filer_name character varying(255),
    filer_cik character varying(20),
    transaction_date timestamp without time zone,
    filing_date timestamp without time zone,
    discovered_at timestamp without time zone DEFAULT now() NOT NULL,
    shares numeric,
    price numeric,
    transaction_value numeric,
    recency_score numeric,
    size_score numeric,
    competence_score numeric,
    consensus_score numeric,
    regime_score numeric,
    total_score numeric,
    conviction_tier character varying(10),
    status character varying(20),
    expires_at timestamp without time zone,
    raw_data json,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.signals OWNER TO dojo;

--
-- Name: signals_id_seq; Type: SEQUENCE; Schema: public; Owner: dojo
--

CREATE SEQUENCE public.signals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.signals_id_seq OWNER TO dojo;

--
-- Name: signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: dojo
--

ALTER SEQUENCE public.signals_id_seq OWNED BY public.signals.id;


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: philosophy_state id; Type: DEFAULT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.philosophy_state ALTER COLUMN id SET DEFAULT nextval('public.philosophy_state_id_seq'::regclass);


--
-- Name: positions id; Type: DEFAULT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.positions ALTER COLUMN id SET DEFAULT nextval('public.positions_id_seq'::regclass);


--
-- Name: signals id; Type: DEFAULT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.signals ALTER COLUMN id SET DEFAULT nextval('public.signals_id_seq'::regclass);


--
-- Data for Name: hypertable; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.hypertable (id, schema_name, table_name, associated_schema_name, associated_table_prefix, num_dimensions, chunk_sizing_func_schema, chunk_sizing_func_name, chunk_target_size, compression_state, compressed_hypertable_id, status) FROM stdin;
\.


--
-- Data for Name: chunk; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.chunk (id, hypertable_id, schema_name, table_name, compressed_chunk_id, dropped, status, osm_chunk, creation_time) FROM stdin;
\.


--
-- Data for Name: chunk_column_stats; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.chunk_column_stats (id, hypertable_id, chunk_id, column_name, range_start, range_end, valid) FROM stdin;
\.


--
-- Data for Name: dimension; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.dimension (id, hypertable_id, column_name, column_type, aligned, num_slices, partitioning_func_schema, partitioning_func, interval_length, compress_interval_length, integer_now_func_schema, integer_now_func) FROM stdin;
\.


--
-- Data for Name: dimension_slice; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.dimension_slice (id, dimension_id, range_start, range_end) FROM stdin;
\.


--
-- Data for Name: chunk_constraint; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.chunk_constraint (chunk_id, dimension_slice_id, constraint_name, hypertable_constraint_name) FROM stdin;
\.


--
-- Data for Name: compression_chunk_size; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.compression_chunk_size (chunk_id, compressed_chunk_id, uncompressed_heap_size, uncompressed_toast_size, uncompressed_index_size, compressed_heap_size, compressed_toast_size, compressed_index_size, numrows_pre_compression, numrows_post_compression, numrows_frozen_immediately) FROM stdin;
\.


--
-- Data for Name: compression_settings; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.compression_settings (relid, compress_relid, segmentby, orderby, orderby_desc, orderby_nullsfirst, index) FROM stdin;
\.


--
-- Data for Name: continuous_agg; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_agg (mat_hypertable_id, raw_hypertable_id, parent_mat_hypertable_id, user_view_schema, user_view_name, partial_view_schema, partial_view_name, direct_view_schema, direct_view_name, materialized_only, finalized) FROM stdin;
\.


--
-- Data for Name: continuous_agg_migrate_plan; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_agg_migrate_plan (mat_hypertable_id, start_ts, end_ts, user_view_definition) FROM stdin;
\.


--
-- Data for Name: continuous_agg_migrate_plan_step; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_agg_migrate_plan_step (mat_hypertable_id, step_id, status, start_ts, end_ts, type, config) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_bucket_function; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_aggs_bucket_function (mat_hypertable_id, bucket_func, bucket_width, bucket_origin, bucket_offset, bucket_timezone, bucket_fixed_width) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_hypertable_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_aggs_hypertable_invalidation_log (hypertable_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_invalidation_threshold; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_aggs_invalidation_threshold (hypertable_id, watermark) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_materialization_invalidation_log; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_aggs_materialization_invalidation_log (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_materialization_ranges; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_aggs_materialization_ranges (materialization_id, lowest_modified_value, greatest_modified_value) FROM stdin;
\.


--
-- Data for Name: continuous_aggs_watermark; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.continuous_aggs_watermark (mat_hypertable_id, watermark) FROM stdin;
\.


--
-- Data for Name: metadata; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.metadata (key, value, include_in_telemetry) FROM stdin;
install_timestamp	2025-10-17 14:23:58.147865+00	t
timescaledb_version	2.22.1	f
exported_uuid	343d84f0-9095-4bab-9126-52e39bfdc41c	t
\.


--
-- Data for Name: tablespace; Type: TABLE DATA; Schema: _timescaledb_catalog; Owner: dojo
--

COPY _timescaledb_catalog.tablespace (id, hypertable_id, tablespace_name) FROM stdin;
\.


--
-- Data for Name: bgw_job; Type: TABLE DATA; Schema: _timescaledb_config; Owner: dojo
--

COPY _timescaledb_config.bgw_job (id, application_name, schedule_interval, max_runtime, max_retries, retry_period, proc_schema, proc_name, owner, scheduled, fixed_schedule, initial_start, hypertable_id, config, check_schema, check_name, timezone) FROM stdin;
\.


--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: dojo
--

COPY public.audit_log (id, "timestamp", event_type, entity_type, entity_id, actor, action, before_state, after_state, event_hash, previous_hash) FROM stdin;
1	2025-10-17 15:04:56.943957	ORDER_CREATED	order	9b2b4ac1-52fa-43f9-a3f2-5abd6cc88b88	SYSTEM	ORDER_CREATED	null	{"order_id": "9b2b4ac1-52fa-43f9-a3f2-5abd6cc88b88", "symbol": "AAPL", "side": "BUY", "quantity": 29, "status": "PENDING", "filled_qty": null, "filled_avg_price": null, "commission": null}	2c32ca78059ac1abceaff95a04a6441ef4eee01c74c27b32515f6834fe7f6c37	GENESIS
2	2025-10-17 15:04:56.968411	ORDER_EXECUTED	order	9b2b4ac1-52fa-43f9-a3f2-5abd6cc88b88	SYSTEM	ORDER_EXECUTED	null	{"order_id": "9b2b4ac1-52fa-43f9-a3f2-5abd6cc88b88", "symbol": "AAPL", "side": "BUY", "quantity": 29, "status": "FILLED", "filled_qty": 29, "filled_avg_price": 96.13558307653325, "commission": 1.0}	e09fef76c52c1051f09ae82bac71f8d37bb6f34e63ecee4b473d0d58e880a628	2c32ca78059ac1abceaff95a04a6441ef4eee01c74c27b32515f6834fe7f6c37
3	2025-10-17 15:04:57.000986	ORDER_CREATED	order	c463005f-d5f7-4a5c-a6f1-eea5eb413e49	SYSTEM	ORDER_CREATED	null	{"order_id": "c463005f-d5f7-4a5c-a6f1-eea5eb413e49", "symbol": "AAPL", "side": "SELL", "quantity": 29, "status": "PENDING", "filled_qty": null, "filled_avg_price": null, "commission": null}	6f6e1584fe5642b43147a6b18e6e39060842ea775ee7086dcfd1e89387b3c552	e09fef76c52c1051f09ae82bac71f8d37bb6f34e63ecee4b473d0d58e880a628
4	2025-10-17 15:04:57.014998	ORDER_EXECUTED	order	c463005f-d5f7-4a5c-a6f1-eea5eb413e49	SYSTEM	ORDER_EXECUTED	null	{"order_id": "c463005f-d5f7-4a5c-a6f1-eea5eb413e49", "symbol": "AAPL", "side": "SELL", "quantity": 29, "status": "FILLED", "filled_qty": 29, "filled_avg_price": 95.13860175504168, "commission": 1.0}	6341abedef1910e63f08e873f89f48b4a2c3c4c425afc78f46f62f7c255170fe	6f6e1584fe5642b43147a6b18e6e39060842ea775ee7086dcfd1e89387b3c552
5	2025-10-17 15:04:57.025198	POSITION_CLOSED	position	POS_TEST_1760713496.919192	SYSTEM	POSITION_CLOSED	null	{"position_id": "POS_TEST_1760713496.919192", "realized_pnl": -28.912458323255517, "return_pct": -0.01037057548918048, "status": "CLOSED"}	2e1cfe397d525472ecd0bd428018e679e101e48760e00db72f1c1c2e13027f58	6341abedef1910e63f08e873f89f48b4a2c3c4c425afc78f46f62f7c255170fe
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: dojo
--

COPY public.orders (id, order_id, broker_order_id, position_id, symbol, side, order_type, quantity, limit_price, stop_price, status, filled_qty, filled_avg_price, commission, submitted_at, filled_at, error_message, created_at, updated_at) FROM stdin;
3	9b2b4ac1-52fa-43f9-a3f2-5abd6cc88b88	119909e0-7e8a-4360-92fd-ee889e186fdc	POS_TEST_1760713496.919192	AAPL	BUY	MARKET	29	\N	\N	FILLED	29	96.13558307653324874793112707	1	2025-10-17 15:04:56.961071	2025-10-17 15:04:56.961071	\N	2025-10-17 15:04:56.932067	2025-10-17 15:04:56.95955
4	c463005f-d5f7-4a5c-a6f1-eea5eb413e49	0b7ec94b-1732-4ff1-a72c-72b8891f4c6d	POS_TEST_1760713496.919192	AAPL	SELL	MARKET	29	\N	\N	FILLED	29	95.13860175504167917248946542	1	2025-10-17 15:04:57.009144	2025-10-17 15:04:57.009144	\N	2025-10-17 15:04:56.99257	2025-10-17 15:04:57.007663
\.


--
-- Data for Name: philosophy_state; Type: TABLE DATA; Schema: public; Owner: dojo
--

COPY public.philosophy_state (id, date, decisions_logged, intuition_overrides, trades_with_safety, trades_without_safety, cluster_signals_detected, cluster_positions_taken, positions_retired, avg_return_per_cycle, positions_extended, avg_sharpe_at_extension, rule_violations, violated_rules, current_allocation_power, created_at, updated_at) FROM stdin;
1	2025-10-17	0	0	0	0	0	0	0	\N	0	\N	0	\N	1.0	2025-10-17 15:00:50.115184	2025-10-17 15:00:50.115184
\.


--
-- Data for Name: positions; Type: TABLE DATA; Schema: public; Owner: dojo
--

COPY public.positions (id, position_id, symbol, direction, entry_date, entry_price, shares, entry_value, source_signals, conviction_tier, philosophy_applied, exit_date, exit_price, exit_value, realized_pnl, return_pct, round_start, round_expiry, round_extended, discipline_violations, status, created_at, updated_at) FROM stdin;
3	POS_TEST_1760713496.919192	AAPL	LONG	2025-10-17 15:04:56.919202	96.13558307653324874793112707	29	2787.931909219464213690002685	{TEST_001}	B	standard	2025-10-17 15:04:57.024904	95.13860175504167917248946542	2759.019450896208696002194497	-28.912458323255517687808188	-0.01037057548918048109063856580	2025-10-17 15:04:56.918557	2025-12-16 15:04:56.918557	f	0	CLOSED	2025-10-17 15:04:56.915883	2025-10-17 15:04:57.021315
\.


--
-- Data for Name: signals; Type: TABLE DATA; Schema: public; Owner: dojo
--

COPY public.signals (id, signal_id, source, symbol, direction, filer_name, filer_cik, transaction_date, filing_date, discovered_at, shares, price, transaction_value, recency_score, size_score, competence_score, consensus_score, regime_score, total_score, conviction_tier, status, expires_at, raw_data, created_at, updated_at) FROM stdin;
4	TEST_001	insider	AAPL	LONG	Test Insider	\N	2025-10-12 15:04:56.895162	2025-10-14 15:04:56.895166	2025-10-17 15:04:56.895167	\N	\N	5000000	0.9666666666666667	0.8	0.5	0.0	0.5	0.6017	B	ACTIVE	\N	\N	2025-10-17 15:04:56.883895	2025-10-17 15:04:56.907563
\.


--
-- Name: chunk_column_stats_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_column_stats_id_seq', 1, false);


--
-- Name: chunk_constraint_name; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_constraint_name', 1, false);


--
-- Name: chunk_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_catalog.chunk_id_seq', 1, false);


--
-- Name: continuous_agg_migrate_plan_step_step_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_catalog.continuous_agg_migrate_plan_step_step_id_seq', 1, false);


--
-- Name: dimension_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_id_seq', 3, true);


--
-- Name: dimension_slice_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_catalog.dimension_slice_id_seq', 1, false);


--
-- Name: hypertable_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_catalog; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_catalog.hypertable_id_seq', 3, true);


--
-- Name: bgw_job_id_seq; Type: SEQUENCE SET; Schema: _timescaledb_config; Owner: dojo
--

SELECT pg_catalog.setval('_timescaledb_config.bgw_job_id_seq', 1000, false);


--
-- Name: audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: dojo
--

SELECT pg_catalog.setval('public.audit_log_id_seq', 5, true);


--
-- Name: orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: dojo
--

SELECT pg_catalog.setval('public.orders_id_seq', 4, true);


--
-- Name: philosophy_state_id_seq; Type: SEQUENCE SET; Schema: public; Owner: dojo
--

SELECT pg_catalog.setval('public.philosophy_state_id_seq', 1, true);


--
-- Name: positions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: dojo
--

SELECT pg_catalog.setval('public.positions_id_seq', 3, true);


--
-- Name: signals_id_seq; Type: SEQUENCE SET; Schema: public; Owner: dojo
--

SELECT pg_catalog.setval('public.signals_id_seq', 4, true);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: orders orders_order_id_key; Type: CONSTRAINT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_order_id_key UNIQUE (order_id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: philosophy_state philosophy_state_date_key; Type: CONSTRAINT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.philosophy_state
    ADD CONSTRAINT philosophy_state_date_key UNIQUE (date);


--
-- Name: philosophy_state philosophy_state_pkey; Type: CONSTRAINT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.philosophy_state
    ADD CONSTRAINT philosophy_state_pkey PRIMARY KEY (id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: dojo
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_log_entity_id; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_audit_log_entity_id ON public.audit_log USING btree (entity_id);


--
-- Name: ix_audit_log_entity_type; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_audit_log_entity_type ON public.audit_log USING btree (entity_type);


--
-- Name: ix_audit_log_timestamp; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_audit_log_timestamp ON public.audit_log USING btree ("timestamp");


--
-- Name: ix_orders_status; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_orders_status ON public.orders USING btree (status);


--
-- Name: ix_positions_position_id; Type: INDEX; Schema: public; Owner: dojo
--

CREATE UNIQUE INDEX ix_positions_position_id ON public.positions USING btree (position_id);


--
-- Name: ix_positions_status; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_positions_status ON public.positions USING btree (status);


--
-- Name: ix_positions_symbol; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_positions_symbol ON public.positions USING btree (symbol);


--
-- Name: ix_signals_signal_id; Type: INDEX; Schema: public; Owner: dojo
--

CREATE UNIQUE INDEX ix_signals_signal_id ON public.signals USING btree (signal_id);


--
-- Name: ix_signals_source; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_signals_source ON public.signals USING btree (source);


--
-- Name: ix_signals_status; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_signals_status ON public.signals USING btree (status);


--
-- Name: ix_signals_symbol; Type: INDEX; Schema: public; Owner: dojo
--

CREATE INDEX ix_signals_symbol ON public.signals USING btree (symbol);


--
-- PostgreSQL database dump complete
--

