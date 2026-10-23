USE college_equipment;

-- Optional manual migration. The Flask app performs the same safe migration automatically.
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS fair_cost DECIMAL(10,2) NOT NULL DEFAULT 250.00 AFTER image_filename;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS damage_cost DECIMAL(10,2) NOT NULL DEFAULT 1000.00 AFTER fair_cost;

-- Good returns do not create a responsibility/cost record.
-- Fair and Damaged return costs are configured per equipment in the Admin/Staff Equipment screen.
