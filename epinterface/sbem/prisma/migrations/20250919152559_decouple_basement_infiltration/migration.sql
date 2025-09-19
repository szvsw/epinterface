/*
  Warnings:

  - Added the required column `BasementInfiltrationId` to the `Envelope` table without a default value. This is not possible if the table is not empty.

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
    "BasementInfiltrationId" TEXT NOT NULL,
    "WindowId" TEXT,
    "MetadataId" TEXT,
    CONSTRAINT "Envelope_AssembliesId_fkey" FOREIGN KEY ("AssembliesId") REFERENCES "EnvelopeAssembly" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_InfiltrationId_fkey" FOREIGN KEY ("InfiltrationId") REFERENCES "Infiltration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_AtticInfiltrationId_fkey" FOREIGN KEY ("AtticInfiltrationId") REFERENCES "Infiltration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_BasementInfiltrationId_fkey" FOREIGN KEY ("BasementInfiltrationId") REFERENCES "Infiltration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Envelope_WindowId_fkey" FOREIGN KEY ("WindowId") REFERENCES "GlazingConstructionSimple" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Envelope_MetadataId_fkey" FOREIGN KEY ("MetadataId") REFERENCES "Metadata" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Envelope" ("AssembliesId", "AtticInfiltrationId", "InfiltrationId", "MetadataId", "Name", "WindowId", "id") SELECT "AssembliesId", "AtticInfiltrationId", "InfiltrationId", "MetadataId", "Name", "WindowId", "id" FROM "Envelope";
DROP TABLE "Envelope";
ALTER TABLE "new_Envelope" RENAME TO "Envelope";
CREATE UNIQUE INDEX "Envelope_Name_key" ON "Envelope"("Name");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
