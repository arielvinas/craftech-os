CREATE TABLE read_request (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id      bigint NOT NULL REFERENCES source (id),
    requested_at   timestamptz NOT NULL DEFAULT now(),
    requested_by   text NOT NULL,
    served_at      timestamptz,
    snapshot_count integer,
    CHECK ((served_at IS NULL) = (snapshot_count IS NULL))
);

-- At most one pending request per source: asking twice is the same request.
CREATE UNIQUE INDEX read_request_pending ON read_request (source_id) WHERE served_at IS NULL;

COMMENT ON TABLE read_request IS 'Pedido de leer ya una planilla ("leer ahora"), sin esperar a que cambie su versión. El worker lo atiende en la vuelta siguiente; hay a lo sumo un pedido pendiente por planilla.';
COMMENT ON COLUMN read_request.id IS 'Identificador interno del pedido.';
COMMENT ON COLUMN read_request.source_id IS 'Planilla que se pidió leer.';
COMMENT ON COLUMN read_request.requested_at IS 'Momento en que se hizo el pedido.';
COMMENT ON COLUMN read_request.requested_by IS 'Desde dónde se pidió: cli (comando craftech-os read-now) o, más adelante, la app web.';
COMMENT ON COLUMN read_request.served_at IS 'Momento en que el worker leyó la planilla; vacío mientras el pedido está pendiente.';
COMMENT ON COLUMN read_request.snapshot_count IS 'Snapshots nuevos que dejó la lectura (cero si ninguna pestaña cambió); vacío mientras el pedido está pendiente.';
