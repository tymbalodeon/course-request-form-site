# CHANGELOG

[AX] = "Admin experience" (Changes relevant mainly to admin users)  
[DX] = "Developer experience" (Changes relevant mainly to developers)

## 2022-01-11

### Fixed

- User's Home view only displays courses from the current or next terms

## 2022-01-10

### Changed

- Removed outdated message about course copy number

## 2022-01-06

### Fixed

- Courses now pull all related sections

## 2021-12-28

### Fixed

- "Copy from course" dropdown now excludes deleted Canvas courses

## 2021-12-27

### Fixed

- List of available courses to copy no longer includes deleted courses

## 2021-12-17

### Changed

- Wording for copy from content to make it clear that you can only select YOUR courses from dropdown

### Fixed

- Restore Instructor as option in additional enrollments

## 2021-12-08

### Fixed

- Additional enrollments in request form page

## 2021-12-07

### Changed

- No longer limit title overrides to 45 characters (increased to 255)

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
