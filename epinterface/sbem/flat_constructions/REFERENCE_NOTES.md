# Semi-flat construction reference notes

This folder intentionally uses simplified/consolidated thermal methods for ML-friendly
inputs. The assumptions below document where steel/wood framing adjustments come from.

## Framed cavity modeling

For framed wall/roof systems we use an equivalent parallel-path layer:

- `U_eq = f_frame / R_frame + (1 - f_frame) / R_fill`
- `R_eq = 1 / U_eq`

For wood framing, `R_frame` is computed directly from framing material conductivity and
cavity depth.

For steel framing, `R_frame` is treated as an **effective framing-path R-value** to
account for 2D/3D heat-flow effects and thermal-bridge behavior not captured by pure
1D steel conductivity. The calibrated values are chosen to reproduce expected effective
batt performance ranges from code-table methods.

## Primary references

1. ASHRAE Standard 90.1 (Appendix A, envelope assembly/U-factor methodology for metal framing)

   - https://www.ashrae.org/technical-resources/bookstore/standard-90-1

2. COMcheck envelope U-factor workflow and datasets (steel-framed assemblies)

   - https://www.energycodes.gov/comcheck

3. PNNL Building America Solution Center (thermal bridging in metal-stud walls)
   - https://basc.pnnl.gov/resource-guides/continuous-insulation-metal-stud-wall

## Scope note

These assumptions are intended for rapid parametric modeling and fixed-length feature
vectors, not project-specific code compliance documentation. For high-fidelity design,
replace defaults with project-calibrated values (e.g., THERM/ISO 10211 workflows).
