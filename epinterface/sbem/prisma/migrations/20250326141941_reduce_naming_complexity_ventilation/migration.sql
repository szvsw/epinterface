/*
  Warnings:

  - You are about to drop the column `DCVType` on the `Ventilation` table. All the data in the column will be lost.
  - You are about to drop the column `EconomizerType` on the `Ventilation` table. All the data in the column will be lost.
  - You are about to drop the column `HRVType` on the `Ventilation` table. All the data in the column will be lost.
  - You are about to drop the column `TechType` on the `Ventilation` table. All the data in the column will be lost.
  - You are about to drop the column `Type` on the `Ventilation` table. All the data in the column will be lost.
  - Added the required column `DCV` to the `Ventilation` table without a default value. This is not possible if the table is not empty.
  - Added the required column `Economizer` to the `Ventilation` table without a default value. This is not possible if the table is not empty.
  - Added the required column `HRV` to the `Ventilation` table without a default value. This is not possible if the table is not empty.
  - Added the required column `Provider` to the `Ventilation` table without a default value. This is not possible if the table is not empty.

*/
-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Ventilation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "FreshAirPerFloorArea" REAL NOT NULL,
    "FreshAirPerPerson" REAL NOT NULL,
    "Provider" TEXT NOT NULL,
    "HRV" TEXT NOT NULL,
    "Economizer" TEXT NOT NULL,
    "DCV" TEXT NOT NULL,
    "MetadataId" TEXT,
    "ScheduleId" TEXT NOT NULL,
    CONSTRAINT "Ventilation_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Ventilation_ScheduleId_fkey" FOREIGN KEY ("ScheduleId") REFERENCES "Year" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_Ventilation" ("FreshAirPerFloorArea", "FreshAirPerPerson", "MetadataId", "Name", "ScheduleId", "id") SELECT "FreshAirPerFloorArea", "FreshAirPerPerson", "MetadataId", "Name", "ScheduleId", "id" FROM "Ventilation";
DROP TABLE "Ventilation";
ALTER TABLE "new_Ventilation" RENAME TO "Ventilation";
CREATE UNIQUE INDEX "Ventilation_Name_key" ON "Ventilation"("Name");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
