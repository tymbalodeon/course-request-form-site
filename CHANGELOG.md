# CHANGELOG

[AX] = "Admin experience" (Changes relevant mainly to admin users)  
[DX] = "Developer experience" (Changes relevant mainly to developers)

## 2021-12-06

### Changed

- Re-worded Multi-Section instructions to make it clear that sections will be grouped in the same site
- No longer display Multi-Section part of form if no sections are available

## 2021-12-01

### Fixed

- [AX] Create Canvas Sites failing when no sections are present

## 2021-11-30

### Fixed

- Auto-adds not enrolling

## 2021-11-29

### Fixed

- Error when data from Data Warehouse has null value for email

## 2021-11-17

### Added

- Pull courses from Open Data as well as DW in the daily sync

### Fixed

- [AX] Data Warehouse Lookup
- [DX] livereload (requires string instead of Path object for template dirs settings)

## 2021-11-16

### Added

- Daily sync for "current" and "next" terms, whose exact values are calculated by the current date

### Changed

- "Copy from existing site" dropdown lists highest Canvas ID number (most recent) first
- "Copy from existing site" searches anywhere in the course title instead of just the beginning of the title
- All autocomplete dropdowns no longer limit to 8 results when searching

### Fixed

- Paginator styles
- Filter function for Request list page
