/*
  Warnings:

  - You are about to drop the column `MinFreshAir` on the `Ventilation` table. All the data in the column will be lost.
  - You are about to drop the column `Rate` on the `Ventilation` table. All the data in the column will be lost.
  - Added the required column `FreshAirPerFloorArea` to the `Ventilation` table without a default value. This is not possible if the table is not empty.
  - Added the required column `FreshAirPerPerson` to the `Ventilation` table without a default value. This is not possible if the table is not empty.

*/
-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Ventilation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "FreshAirPerFloorArea" REAL NOT NULL,
    "FreshAirPerPerson" REAL NOT NULL,
    "Type" TEXT NOT NULL,
    "TechType" TEXT NOT NULL,
    "MetadataId" TEXT,
    "ScheduleId" TEXT NOT NULL,
    CONSTRAINT "Ventilation_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Ventilation_ScheduleId_fkey" FOREIGN KEY ("ScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_Ventilation" ("MetadataId", "Name", "ScheduleId", "TechType", "Type", "id") SELECT "MetadataId", "Name", "ScheduleId", "TechType", "Type", "id" FROM "Ventilation";
DROP TABLE "Ventilation";
ALTER TABLE "new_Ventilation" RENAME TO "Ventilation";
CREATE UNIQUE INDEX "Ventilation_Name_key" ON "Ventilation"("Name");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
