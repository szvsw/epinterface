/*
  Warnings:

  - You are about to drop the `RepeatedWeek` table. If the table is not empty, all the data it contains will be lost.
  - Added the required column `AprilId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `AugustId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `DecemberId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `FebruaryId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `JanuaryId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `JulyId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `JuneId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `MarchId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `MayId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `NovemberId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `OctoberId` to the `Year` table without a default value. This is not possible if the table is not empty.
  - Added the required column `SeptemberId` to the `Year` table without a default value. This is not possible if the table is not empty.

*/
-- DropTable
PRAGMA foreign_keys=off;
DROP TABLE "RepeatedWeek";
PRAGMA foreign_keys=on;

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Year" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Type" TEXT NOT NULL,
    "JanuaryId" TEXT NOT NULL,
    "FebruaryId" TEXT NOT NULL,
    "MarchId" TEXT NOT NULL,
    "AprilId" TEXT NOT NULL,
    "MayId" TEXT NOT NULL,
    "JuneId" TEXT NOT NULL,
    "JulyId" TEXT NOT NULL,
    "AugustId" TEXT NOT NULL,
    "SeptemberId" TEXT NOT NULL,
    "OctoberId" TEXT NOT NULL,
    "NovemberId" TEXT NOT NULL,
    "DecemberId" TEXT NOT NULL,
    CONSTRAINT "Year_JanuaryId_fkey" FOREIGN KEY ("JanuaryId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_FebruaryId_fkey" FOREIGN KEY ("FebruaryId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_MarchId_fkey" FOREIGN KEY ("MarchId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_AprilId_fkey" FOREIGN KEY ("AprilId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_MayId_fkey" FOREIGN KEY ("MayId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_JuneId_fkey" FOREIGN KEY ("JuneId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_JulyId_fkey" FOREIGN KEY ("JulyId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_AugustId_fkey" FOREIGN KEY ("AugustId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_SeptemberId_fkey" FOREIGN KEY ("SeptemberId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_OctoberId_fkey" FOREIGN KEY ("OctoberId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_NovemberId_fkey" FOREIGN KEY ("NovemberId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Year_DecemberId_fkey" FOREIGN KEY ("DecemberId") REFERENCES "Week" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_Year" ("Name", "Type", "id") SELECT "Name", "Type", "id" FROM "Year";
DROP TABLE "Year";
ALTER TABLE "new_Year" RENAME TO "Year";
CREATE UNIQUE INDEX "Year_Name_key" ON "Year"("Name");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
