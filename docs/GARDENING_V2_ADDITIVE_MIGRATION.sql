-- Cape Ranch Gardening V2 additive DDL (PostgreSQL 17/18).
-- Run ONLY against an approved testing/production DB after a verified backup.
-- Existing v6_garden_areas and v6_garden_records remain unchanged.
BEGIN;


CREATE TABLE IF NOT EXISTS v11_garden_plants (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	variety VARCHAR(120), 
	quantity INTEGER NOT NULL, 
	planted_on DATE, 
	source VARCHAR(160), 
	unit_purchase_cost NUMERIC(18, 2) NOT NULL, 
	currency VARCHAR(8) NOT NULL, 
	condition VARCHAR(32) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES v5_organizations (id), 
	FOREIGN KEY(area_id) REFERENCES v6_garden_areas (id)
)

;
CREATE INDEX IF NOT EXISTS ix_v11_garden_plants_organization_id ON v11_garden_plants (organization_id);
CREATE INDEX IF NOT EXISTS ix_v11_garden_plant_org_area ON v11_garden_plants (organization_id, area_id);


CREATE TABLE IF NOT EXISTS v11_garden_nursery_batches (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	plant_name VARCHAR(160) NOT NULL, 
	method VARCHAR(30) NOT NULL, 
	started_on DATE NOT NULL, 
	seeds_started INTEGER NOT NULL, 
	germinated INTEGER NOT NULL, 
	survived INTEGER NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES v5_organizations (id), 
	FOREIGN KEY(area_id) REFERENCES v6_garden_areas (id)
)

;
CREATE INDEX IF NOT EXISTS ix_v11_garden_nursery_batches_organization_id ON v11_garden_nursery_batches (organization_id);


CREATE TABLE IF NOT EXISTS v11_garden_schedules (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	action VARCHAR(32) NOT NULL, 
	frequency VARCHAR(24) NOT NULL, 
	shift VARCHAR(24) NOT NULL, 
	assigned_to INTEGER, 
	starts_on DATE NOT NULL, 
	ends_on DATE, 
	is_active BOOLEAN NOT NULL, 
	instructions TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES v5_organizations (id), 
	FOREIGN KEY(area_id) REFERENCES v6_garden_areas (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_v11_garden_schedules_organization_id ON v11_garden_schedules (organization_id);


CREATE TABLE IF NOT EXISTS v11_garden_work (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	schedule_id INTEGER, 
	plant_id INTEGER, 
	action VARCHAR(32) NOT NULL, 
	performed_on DATE NOT NULL, 
	shift VARCHAR(24) NOT NULL, 
	water_litres NUMERIC(16, 2) NOT NULL, 
	area_covered_m2 NUMERIC(14, 2) NOT NULL, 
	labor_hours NUMERIC(12, 2) NOT NULL, 
	direct_cost NUMERIC(18, 2) NOT NULL, 
	currency VARCHAR(8) NOT NULL, 
	observations TEXT, 
	recorded_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_v11_garden_schedule_day UNIQUE (schedule_id, performed_on), 
	FOREIGN KEY(organization_id) REFERENCES v5_organizations (id), 
	FOREIGN KEY(area_id) REFERENCES v6_garden_areas (id), 
	FOREIGN KEY(schedule_id) REFERENCES v11_garden_schedules (id), 
	FOREIGN KEY(plant_id) REFERENCES v11_garden_plants (id), 
	FOREIGN KEY(recorded_by) REFERENCES users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_v11_garden_work_organization_id ON v11_garden_work (organization_id);
CREATE INDEX IF NOT EXISTS ix_v11_garden_work_org_date ON v11_garden_work (organization_id, performed_on);


CREATE TABLE IF NOT EXISTS v11_garden_health (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	plant_id INTEGER, 
	observed_on DATE NOT NULL, 
	issue VARCHAR(160) NOT NULL, 
	severity VARCHAR(24) NOT NULL, 
	affected_count INTEGER NOT NULL, 
	treatment TEXT, 
	follow_up_on DATE, 
	status VARCHAR(24) NOT NULL, 
	expense NUMERIC(18, 2) NOT NULL, 
	currency VARCHAR(8) NOT NULL, 
	recorded_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES v5_organizations (id), 
	FOREIGN KEY(area_id) REFERENCES v6_garden_areas (id), 
	FOREIGN KEY(plant_id) REFERENCES v11_garden_plants (id), 
	FOREIGN KEY(recorded_by) REFERENCES users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_v11_garden_health_organization_id ON v11_garden_health (organization_id);


CREATE TABLE IF NOT EXISTS v11_garden_expenses (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	spent_on DATE NOT NULL, 
	category VARCHAR(32) NOT NULL, 
	description VARCHAR(200) NOT NULL, 
	quantity NUMERIC(14, 3) NOT NULL, 
	unit VARCHAR(32) NOT NULL, 
	unit_cost NUMERIC(18, 2) NOT NULL, 
	other_cost NUMERIC(18, 2) NOT NULL, 
	total_cost NUMERIC(18, 2) NOT NULL, 
	currency VARCHAR(8) NOT NULL, 
	inventory_item_id INTEGER, 
	notes TEXT, 
	recorded_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES v5_organizations (id), 
	FOREIGN KEY(area_id) REFERENCES v6_garden_areas (id), 
	FOREIGN KEY(recorded_by) REFERENCES users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_v11_garden_expenses_organization_id ON v11_garden_expenses (organization_id);


CREATE TABLE IF NOT EXISTS v11_garden_inspections (
	id SERIAL NOT NULL, 
	organization_id INTEGER NOT NULL, 
	area_id INTEGER NOT NULL, 
	inspected_on DATE NOT NULL, 
	cleanliness INTEGER NOT NULL, 
	plant_health INTEGER NOT NULL, 
	weed_control INTEGER NOT NULL, 
	irrigation INTEGER NOT NULL, 
	overall_score NUMERIC(4, 2) NOT NULL, 
	corrective_action TEXT, 
	follow_up_on DATE, 
	inspected_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES v5_organizations (id), 
	FOREIGN KEY(area_id) REFERENCES v6_garden_areas (id), 
	FOREIGN KEY(inspected_by) REFERENCES users (id)
)

;
CREATE INDEX IF NOT EXISTS ix_v11_garden_inspections_organization_id ON v11_garden_inspections (organization_id);

COMMIT;
