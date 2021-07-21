#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER d3a_profiles_user;
    CREATE DATABASE d3a_profiles;
    GRANT ALL PRIVILEGES ON DATABASE d3a_profiles TO d3a_profiles_user;
    \c d3a_profiles d3a_profiles_user
    CREATE TABLE "configurationareaprofileuuids" (
       "id" SERIAL PRIMARY KEY,
       "configuration_uuid" TEXT NOT NULL,
       "area_uuid" TEXT NOT NULL,
       "profile_uuid" TEXT NOT NULL,
       "profile_type" INTEGER NOT NULL
    );
    CREATE TABLE "profiletimeseries" (
        "id" SERIAL PRIMARY KEY,
        "profile_uuid" TEXT NOT NULL,
        "time" TIMESTAMP NOT NULL,
        "value" DOUBLE PRECISION NOT NULL
    );
EOSQL