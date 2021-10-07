#!/bin/bash
set -e

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER d3a_profiles_user;
    CREATE DATABASE d3a_profiles;
    GRANT ALL PRIVILEGES ON DATABASE d3a_profiles TO d3a_profiles_user;
    \c d3a_profiles d3a_profiles_user
    CREATE TABLE "profile_database_configurationareaprofileuuids" (
       "id" SERIAL PRIMARY KEY,
       "configuration_uuid" UUID NOT NULL,
       "area_uuid" UUID NOT NULL,
       "profile_uuid" UUID NOT NULL,
       "profile_type" INTEGER NOT NULL
    );
    CREATE TABLE "profile_database_profiletimeseries" (
        "id" SERIAL PRIMARY KEY,
        "profile_uuid" UUID NOT NULL,
        "time" TIMESTAMP NOT NULL,
        "value" DOUBLE PRECISION NOT NULL
    );
EOSQL
