/*
  Warnings:

  - You are about to drop the column `FacadeIsAdiabatic` on the `EnvelopeAssembly` table. All the data in the column will be lost.
  - You are about to drop the column `GroundIsAdiabatic` on the `EnvelopeAssembly` table. All the data in the column will be lost.
  - You are about to drop the column `PartitionIsAdiabatic` on the `EnvelopeAssembly` table. All the data in the column will be lost.
  - You are about to drop the column `RoofAssemblyId` on the `EnvelopeAssembly` table. All the data in the column will be lost.
  - You are about to drop the column `RoofIsAdiabatic` on the `EnvelopeAssembly` table. All the data in the column will be lost.
  - You are about to drop the column `SlabAssemblyId` on the `EnvelopeAssembly` table. All the data in the column will be lost.
  - You are about to drop the column `SlabIsAdiabatic` on the `EnvelopeAssembly` table. All the data in the column will be lost.
  - Added the required column `AtticInfiltrationId` to the `Envelope` table without a default value. This is not possible if the table is not empty.
  - Added the required column `AtticFloorAssemblyId` to the `EnvelopeAssembly` table without a default value. This is not possible if the table is not empty.
  - Added the required column `AtticRoofAssemblyId` to the `EnvelopeAssembly` table without a default value. This is not possible if the table is not empty.
  - Added the required column `BasementCeilingAssemblyId` to the `EnvelopeAssembly` table without a default value. This is not possible if the table is not empty.
  - Added the required column `FlatRoofAssemblyId` to the `EnvelopeAssembly` table without a default value. This is not possible if the table is not empty.
  - Added the required column `FloorCeilingAssemblyId` to the `EnvelopeAssembly` table without a default value. This is not possible if the table is not empty.

*/
-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Envelope" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "AssembliesId" TEXT NOT NULL,
    "InfiltrationId" TEXT NOT NULL,
    "AtticInfiltrationId" TEXT NOT NULL,
    "WindowId" TEXT,
    "MetadataId" TEXT,
    CONSTRAINT "Envelope_AssembliesId_fkey" FOREIGN KEY ("AssembliesId") REFERENCES "EnvelopeAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_InfiltrationId_fkey" FOREIGN KEY ("InfiltrationId") REFERENCES "Infiltration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_AtticInfiltrationId_fkey" FOREIGN KEY ("AtticInfiltrationId") REFERENCES "Infiltration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_WindowId_fkey" FOREIGN KEY ("WindowId") REFERENCES "GlazingConstructionSimple" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Envelope_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Envelope" ("AssembliesId", "InfiltrationId", "MetadataId", "Name", "WindowId", "id") SELECT "AssembliesId", "InfiltrationId", "MetadataId", "Name", "WindowId", "id" FROM "Envelope";
DROP TABLE "Envelope";
ALTER TABLE "new_Envelope" RENAME TO "Envelope";
CREATE UNIQUE INDEX "Envelope_Name_key" ON "Envelope"("Name");
CREATE TABLE "new_EnvelopeAssembly" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "InternalMassExposedAreaPerArea" REAL,
    "FlatRoofAssemblyId" TEXT NOT NULL,
    "AtticRoofAssemblyId" TEXT NOT NULL,
    "AtticFloorAssemblyId" TEXT NOT NULL,
    "FacadeAssemblyId" TEXT NOT NULL,
    "FloorCeilingAssemblyId" TEXT NOT NULL,
    "PartitionAssemblyId" TEXT NOT NULL,
    "ExternalFloorAssemblyId" TEXT NOT NULL,
    "GroundSlabAssemblyId" TEXT NOT NULL,
    "GroundWallAssemblyId" TEXT NOT NULL,
    "BasementCeilingAssemblyId" TEXT NOT NULL,
    "InternalMassAssemblyId" TEXT,
    "MetadataId" TEXT,
    CONSTRAINT "EnvelopeAssembly_FlatRoofAssemblyId_fkey" FOREIGN KEY ("FlatRoofAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_AtticRoofAssemblyId_fkey" FOREIGN KEY ("AtticRoofAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_AtticFloorAssemblyId_fkey" FOREIGN KEY ("AtticFloorAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_FacadeAssemblyId_fkey" FOREIGN KEY ("FacadeAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_FloorCeilingAssemblyId_fkey" FOREIGN KEY ("FloorCeilingAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_PartitionAssemblyId_fkey" FOREIGN KEY ("PartitionAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_ExternalFloorAssemblyId_fkey" FOREIGN KEY ("ExternalFloorAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_GroundSlabAssemblyId_fkey" FOREIGN KEY ("GroundSlabAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_GroundWallAssemblyId_fkey" FOREIGN KEY ("GroundWallAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_BasementCeilingAssemblyId_fkey" FOREIGN KEY ("BasementCeilingAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_InternalMassAssemblyId_fkey" FOREIGN KEY ("InternalMassAssemblyId") REFERENCES "ConstructionAssembly" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "EnvelopeAssembly_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_EnvelopeAssembly" ("ExternalFloorAssemblyId", "FacadeAssemblyId", "GroundSlabAssemblyId", "GroundWallAssemblyId", "InternalMassAssemblyId", "InternalMassExposedAreaPerArea", "MetadataId", "Name", "PartitionAssemblyId", "id") SELECT "ExternalFloorAssemblyId", "FacadeAssemblyId", "GroundSlabAssemblyId", "GroundWallAssemblyId", "InternalMassAssemblyId", "InternalMassExposedAreaPerArea", "MetadataId", "Name", "PartitionAssemblyId", "id" FROM "EnvelopeAssembly";
DROP TABLE "EnvelopeAssembly";
ALTER TABLE "new_EnvelopeAssembly" RENAME TO "EnvelopeAssembly";
CREATE UNIQUE INDEX "EnvelopeAssembly_Name_key" ON "EnvelopeAssembly"("Name");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
