

clear 
clear matrix
set more off
****************************************************************************

****************************************************************************
*Set the directory 
cd "/Users/sarahlowder/Desktop/00 FSEC/03 FSEC policy database - building it/00March30"
									
									
									//FAPDA
//import excel "fapda_data.xlsx", sheet("Report") firstrow case(lower) clear
import excel "fapda_policy_decision_data_202203301529_2.xlsx", sheet("Report") firstrow case(lower) clear


//Cleaning
ren policyclassification country
ren region FAPDA_region
ren subregion FAPDA_subregion
gen y_start =  substr(initialdate, -4, 4)
destring y_start, replace
gen y_end = year(enddate)

//Create id
gen id = _n
order id, first
ren policy1 policy_description1
ren policy2 policy_description2
ren policycode1 policy_code1
ren policycode2 policy_code2

//I DON'T think we need to worry about policy_description2
//One policy description per line
//reshape long policy_code, i(id) j(policy_part)
//replace policy_description1 = policy_description2 if policy_part == 2
drop policy_code2
rename policy_code1 policy_code
drop if policy_code == ""
drop policy_description2
ren policy_description1 policy_description

//Consistent names
replace country = "Bahamas, The" if country == "Bahamas"
replace country = "Cabo Verde" if country == "Cape Verde"
replace country = "Congo, Dem. Rep." if country == "Congo (Democratic Republic of)"
replace country = "Cote d'Ivoire" if country == "Côte d'Ivoire"
replace country = "Egypt, Arab Rep." if country == "Egypt"
replace country = "Iran, Islamic Rep." if country == "Iran  (Islamic Republic of)"
replace country = "Korea, Dem. People's Rep." if country == "Korea (Democratic People’s Republic of)"
replace country = "Korea, Rep." if country == "Korea (Republic of)"
replace country = "Kyrgyz Republic" if country == "Kyrgyzstan"
replace country = "Lao PDR" if country == "Lao People's Democratic Republic"
replace country = "Micronesia, Fed. Sts." if country == "Micronesia (Federated States of)"
replace country = "Moldova" if country == "Moldova (Republic of)"
replace country = "Serbia and Montenegro" if country == "Montenegro"
replace country = "St. Kitts and Nevis" if country == "Saint Kitts and Nevis"
replace country = "St. Lucia" if country == "Saint Lucia"
replace country = "St. Vincent and the Grenadines" if country == "Saint Vincent and the Grenadines"
replace country = "Serbia and Montenegro" if country == "Serbia (Republic of)"
replace country = "Slovak Republic" if country == "Slovakia"
replace country = "Tanzania" if country == "Tanzania (United Republic of)"
replace country = "North Macedonia" if country == "The former Yugoslav Republic of Macedonia"
replace country = "United Kingdom" if country == "U.K. of Great Britain and Northern Ireland"
replace country = "United States" if country == "United States of America"
replace country = "Venezuela, RB" if country == "Venezuela (Bolivarian Republic of)"
replace country = "Vietnam" if country == "Viet Nam"
replace country = "Yemen, Rep." if country == "Yemen"

//Add iso codes
merge m:1 country using "iso.dta"
order iso, before(country)
order y_start, after(country)
order y_end, after(y_start)
ren policydecisiondetails policydecision_details
save "fapda_data.dta", replace

//Rules
import excel "fapda_rules.xlsx", sheet("Sheet1") firstrow case(lower) clear
drop if policycode1 == .
replace proposedsegment = strtrim(proposedsegment)
replace proposedlevertype = strtrim(proposedlevertype)
drop toolboxsegment toolboxlevertype didfapdaincludeexamplefromb
ren policycode1 policy_code
ren policy1 policy_description
rename proposedsegment segment
rename proposedlevertype lever
sort policy_code policy_description
quietly by policy_code policy_description:  gen dup = cond(_N==1,0,_n)
drop if dup == 2 & policy_code == 1400
drop if dup == 1 & policy_code == 2120
drop if dup == 2 & policy_code == 1230
drop if policy_code == 1320 & policy_description != ""
replace policy_description = "Price control" if policy_description == "" & policy_code == 1320
drop dup
save "fapda_rules.dta", replace

//Merge
use "fapda_data.dta", clear
drop if _merge == 2
drop _merge
destring policy_code, replace
merge m:1 policy_code policy_description using "fapda_rules.dta"
drop if _merge != 3
drop _merge
gen db = "FAPDA"
drop if lever == "delete"

// Note: here manual classification
drop if strpos(lever, "manual")
save "fapda_m.dta", replace


								// FAPDA Frameworks
								
import excel "fapda_f_data.xlsx", sheet("Sheet0") firstrow case(lower) clear
ren region FAPDA_region
ren subregion FAPDA_subregion
ren fromdate y_start
ren todate y_end
ren dateofadoption initialdate
ren typeofpolicydocument policydirection
gen db = "FAPDA_F"
ren description policydecision_details
ren additionalinformation contextoradditionalinfo
ren title policy_description
ren sourcename source1name
ren sourcelink source1link
drop if id == ""
drop if id == "Food and Agriculture Policy Framework Analysis Tool"
drop id
gen id = _n
drop policycategorycode7 policycategory7 policycategorycode8 policycategory8 policycategorycode9 policycategory9 policycategorycode10 policycategory10
reshape long policycategory policycategorycode, i(id) j(policy_part)
drop if policycategorycode == 0

//Consistent names
replace country = "Bahamas, The" if country == "Bahamas"
replace country = "Cabo Verde" if country == "Cape Verde"
replace country = "Congo, Dem. Rep." if country == "Congo (Democratic Republic of)"
replace country = "Cote d'Ivoire" if country == "Côte d'Ivoire"
replace country = "Egypt, Arab Rep." if country == "Egypt"
replace country = "Iran, Islamic Rep." if country == "Iran  (Islamic Republic of)"
replace country = "Korea, Dem. People's Rep." if country == "Korea (Democratic People’s Republic of)"
replace country = "Korea, Dem. People's Rep." if strpos(country,"Korea (Democratic Peo")
replace country = "Korea, Rep." if country == "Korea (Republic of)"
replace country = "Kyrgyz Republic" if country == "Kyrgyzstan"
replace country = "Lao PDR" if country == "Lao People's Democratic Republic"
replace country = "Micronesia, Fed. Sts." if country == "Micronesia (Federated States of)"
replace country = "Moldova" if country == "Moldova (Republic of)"
replace country = "Serbia and Montenegro" if country == "Montenegro"
replace country = "St. Kitts and Nevis" if country == "Saint Kitts and Nevis"
replace country = "St. Lucia" if country == "Saint Lucia"
replace country = "St. Vincent and the Grenadines" if country == "Saint Vincent and the Grenadines"
replace country = "Serbia and Montenegro" if country == "Serbia (Republic of)"
replace country = "Slovak Republic" if country == "Slovakia"
replace country = "Tanzania" if country == "Tanzania (United Republic of)"
replace country = "North Macedonia" if country == "The former Yugoslav Republic of Macedonia"
replace country = "United Kingdom" if country == "U.K. of Great Britain and Northern Ireland"
replace country = "United States" if country == "United States of America"
replace country = "Venezuela, RB" if country == "Venezuela (Bolivarian Republic of)"
replace country = "Vietnam" if country == "Viet Nam"
replace country = "Yemen, Rep." if country == "Yemen"

//Add iso codes
merge m:1 country using "iso.dta"
order iso, before(country)
drop if _merge == 2
drop _merge
save "fapda_f_data.dta", replace

//Rules
import excel "fapda_f_rules.xlsx", sheet("Sheet1") firstrow case(lower) clear
save "fapda_f_rules.dta", replace

//Merge
use fapda_f_data.dta, clear
merge m:1 policycategory using fapda_f_rules.dta
drop if _merge != 3
drop _merge
save "fapda_f_m.dta", replace


								// NOURISHING
								
import excel "nour_data.xlsx", sheet("Sheet2") cellrange(A2:F848) firstrow case(lower) clear
ren type db
replace country = "Bahamas, The" if country == "Bahamas"
replace country = "Hong Kong SAR, China" if country == "Hong Kong"
replace country = "Brunei Darussalam" if country == "Brunei"
replace country = "Iran, Islamic Rep." if country == "Iran"
replace country = "North Macedonia" if country == "Macedonia"
replace country = "Micronesia, Fed. Sts." if country == "Micronesia"
replace country = "Russian Federation" if country == "Russia"
replace country = "Slovak Republic" if country == "Slovakia"
replace country = "Korea, Rep." if country == "South Korea"
replace country = "St. Kitts and Nevis" if country == "St Kitts and Nevis"
replace country = "St. Lucia" if country == "St Lucia"
replace country = "St. Helena" if country == "St Helena"
replace country = "St. Vincent and the Grenadines" if country == "St Vincent and the Grenadines"
replace country = "United Arab Emirates" if country == "UAE"
replace country = "Venezuela, RB" if country == "Venezuela"
replace country = "United Kingdom" if country == "UK"
replace country = "United States" if country == "USA"
merge m:1 country using "iso.dta"
replace country = "Germany" if _merge == 1 & topic == "Schools"
replace country = "Norway" if _merge == 1 & topic == ", Children, Fruit and veg, Wholegrain"
replace iso = "DEU" if country == "Germany"
replace iso = "NOR" if country == "Norway"
drop if _merge == 2
drop _merge
ren policyaction policydecision_details
ren policyarea policy_description
ren subpolicyarea contextoradditionalinfo
save "nour_data.dta", replace

//Rules
import excel "nour_rules.xlsx", sheet("Sheet1") firstrow case(lower) clear
rename proposedsegment segment
rename proposedlever lever
ren policyarea policy_description
ren subarea contextoradditionalinfo
save "nour_rules.dta", replace

//Merge
use "nour_data.dta", clear
merge m:1 policy_description contextoradditionalinfo using "nour_rules.dta"
drop if _merge != 3
drop _merge
//drop if needtocheckmanually == 1
save "nour_m.dta", replace

							// PINE

//Merging all 3

use fapda_m.dta, clear
append using nour_m.dta, force
append using pine_m.dta, force
append using fapda_f_m.dta, force

replace segment = lower(segment)

drop S T U V W X Y Z AA AB AC AD AE AF AG AH AI AJ AK AL AM AN AO AP AQ AR AS AT AU
gen level = ""

//drop needtocheckmanually
drop id
sort db
gen id = _n
replace segment = "manual" if needtocheckmanually != ""
replace segment = "processing and manuf" if segment == "processing and manufacturing"
replace segment = "food service" if segment == "food_service"
replace segment = "distribution/transport" if segment == "distribution/ transport"
//gen keep = 1 if inlist(segment, "inputs", "farming", "distribution/transport", "trade", //"processing and manuf", "retail", "food service", "eating", "research_tech")
//replace keep = 1 if segment == "manual"
//drop if keep != 1
//drop keep
gen checkme = 1
replace checkme = 0 if inlist(segment, "inputs", "farming", "distribution/transport", "trade", "processing and manuf", "retail", "food service", "eating", "research_tech")
order id, first

//Merge with OECD

merge m:1 iso using oecd.dta
drop if _merge==2
drop _merge

//Merge with WB regions and income levels

merge m:1 iso using WB_CLASS.dta
drop if _merge == 2
drop _merge
gen covid_mentioned = 1 if strpos(policydecision_details, "COVID") | strpos(policydecision_details, "Covid") | strpos(policydecision_details, "covid")
replace lever = "Tax on unhealthy foods" if lever == "taxes" & db == "Nourishing"
replace lever = "subsidy" if lever == "subsidies"

save all_manual.dta, replace

//Create level (national/subnational/supranational) using the python script

//import excel "all_manual.xls", sheet("Sheet1") firstrow clear
//replace level = "Supranational" if iso == ""
//drop A

//some more cleaning
//drop if segment == "multiple"
replace lever = "ag mkt intervention" if lever == "ag market intervention"
replace lever = "emission rights" if lever == "emissions trading scheme re forests"
replace lever = "Fee (affh)" if lever == "Fee forests" | lever == "Fee fishing forestry  hunting" | lever == "Fee fishing and hunting" | lever == "Fee fishing"
replace lever = "Fee (affh)" if lever == "Fee" & segment == "farming"
replace lever = "Subsidies (for production)" if lever == "subsidy" & segment == "farming"
replace lever = "procurement rules/ standards" if strpos(lever, "procurement rules/ standards - but this doesn't emphasize the local procurement aspect…")
replace lever = "Tax on inputs" if lever == "taxes on inputs"
replace lever = "rules on composition/ reformulation" if lever == "Rules on Composition/Reformulation"
replace lever = "Other trade-related measures" if lever == "Other measures that affect exports" | lever == "Other measures that affect imports" | lever == "Other trade and trade-related measures"
replace lever = "Sanitary and Phytosanitary measures (SPS)" if lever == "Sanitary, phytosanitary and technical standards improvements"
drop if lever == "voluntary agreement" & segment == "farming"

foreach var of varlist(policy_description policydecision_details contextoradditionalinfo generaltaxbase specifictaxbase exemptiontype exemptiondetails earmarking){
replace foodwaste = 1 if strpos(`var', "food waste")
replace foodwaste = 1 if strpos(`var', "Food waste")
replace foodwaste = 1 if strpos(`var', "food loss")
replace foodwaste = 1 if strpos(`var', "Food loss")
replace foodwaste = 1 if strpos(`var', "FLW")
replace foodwaste = 1 if strpos(`var', "flw")
replace foodwaste = 1 if strpos(`var', "Flw")
}
save all_manual.dta, replace

//Merge with the Food Systems Dashboard's types

import delimited "clusters_FSD.csv", clear
ren v1 country
ren v2 fsd_group
drop if country == "Montenegro"

replace country = "Bahamas, The" if country == "Bahamas"
replace country = "Congo, Dem. Rep." if country == "Congo"
replace country = "Cote d'Ivoire" if country == "Côte d’Ivoire"
replace country = "Egypt, Arab Rep." if country == "Egypt"
replace country = "Iran, Islamic Rep." if country == "Iran"
replace country = "Korea, Rep." if country == "Korea Rep"
replace country = "Kyrgyz Republic" if country == "Kyrgyzstan"
replace country = "Serbia and Montenegro" if country == "Serbia"
replace country = "Venezuela, RB" if country == "Venezuela"
replace country = "Vietnam" if country == "Viet Nam"
replace country = "Yemen, Rep." if country == "Yemen"
replace country = "Russian Federation" if country == "Russia"
replace country = "Cabo Verde" if country == "Cape Verde"
replace country = "Hong Kong SAR, China" if country == "Hong Kong"
replace country = "Brunei Darussalam" if country == "Brunei"
replace country = "Iran, Islamic Rep." if country == "Iran"
replace country = "North Macedonia" if country == "Macedonia"
replace country = "Micronesia, Fed. Sts." if country == "Micronesia"
replace country = "Russian Federation" if country == "Russia"
replace country = "Slovak Republic" if country == "Slovakia"
replace country = "Moldova" if country == "Republic of Moldova"
replace country = "Eswatini" if country == "Swaziland"
replace country = "Korea, Rep." if country == "South Korea"
replace country = "St. Kitts and Nevis" if country == "St Kitts and Nevis"
replace country = "St. Lucia" if country == "Saint Lucia"
replace country = "St. Helena" if country == "St Helena"
replace country = "St. Vincent and the Grenadines" if country == "St Vincent and the Grenadines"
replace country = "United Arab Emirates" if country == "UAE"
replace country = "Venezuela, RB" if country == "Venezuela"
replace country = "United Kingdom" if country == "UK"
replace country = "United States" if country == "United States Of America"

merge 1:1 country using iso.dta
drop if _merge == 2
drop _merge
drop country
save clusters_fsd.dta, replace

use all_manual.dta, clear
merge m:1 iso using clusters_fsd.dta
drop if _merge == 2
drop _merge

replace segment = strtrim(segment)
replace segment = "01inputs" if segment == "inputs"
replace segment = "02farming" if segment == "farming"
replace segment = "03distribution/transport" if segment == "distribution/transport"
replace segment = "04trade" if segment == "trade"
replace segment = "05processing/manuf" if segment == "processing and manuf"
replace segment = "06retail" if segment == "retail"
replace segment = "07foodservice" if segment == "food service"
replace segment = "08eating" if segment == "eating"
//replace segment = "09foodwaste" if foodwaste == 1

/*Creating expired category
drop expired
gen expired = 0
replace expired = 1 if y_start < 2000
replace expired = 1 if y_end < 2015
replace expired = 1 if strpos(yearoflastrevision, "abolished")
*/
//Renaming levers
replace lever = "xx General input measures" if lever == "General input measures"
replace lever = "x Market intervention: local input production/provision" if lever == "market intervention: local input production/ provision"
replace lever = "x Exemption, reduction or increase in tax on ag inputs" if lever == "Tax on inputs" & segment == "01inputs"
replace lever = "Finance and credit" if policy_code == 2130 | policy_code == 2131 | policy_code == 2132
replace lever = "Ag insurance or risk management" if policy_code == 2210 | policy_code == 2211 | policy_code == 2212 | policy_code == 2213
replace lever = "Management of natural resources" if lever == "rules on natural resource management"
replace lever = "Value chain - support for farmer or community markets" if lever == "support for short supply chains"
replace lever = "Value chain - rural roads and transport infrastructure" if lever == "ag mkt intervention (storage infrastructure and distribution support)"
replace lever = "Import - antidumping duties, countervailing duties, etc" if lever == "Anti-dumping duties, countervailing duties, safeguard measures"
replace lever = "Export - other export promotion measures" if lever == "Other export promotion measures"
replace lever = "Export - other export restrictions" if lever == "Other export restrictions"
replace lever = "Import - other import restrictions" if lever == "Other import restrictions"
replace lever = "Import - non tariff barrier - sanitary phytosanitary measures (SPS)" if lever == "Sanitary and Phytosanitary measures (SPS)"
replace lever = "Import - tariff-rate quota" if lever == "Tariff-rate quota"
replace lever = "Import - non tariff barrier - technical barriers to trade" if lever == "Technical barriers to trade"
replace lever = "Value chain - processing and post production facilities" if lever == "Processing and post-production facilities"
replace lever = "DH - breastfeeding promotion" if lever == "Breastfeeding promotion"
replace lever = "FA - cash for work" if lever == "Cash-for-work"
replace lever = "Beverage container deposit refund" if lever == "deposit refund for bev container"
replace lever = "DH - dietary guidelines" if lever == "dietary guidelines"
replace lever = "DH - education" if lever == "education"
replace lever = "Beverage container fee" if lever == "Fee on container"
replace lever = "FA - food coupons" if lever == "Food coupons"
replace lever = "FA - food for work" if lever == "Food- for -work"
replace lever = "Other - governance/ institutions" if lever == "governance/ institutions"
replace lever = "FA - in kind food transfer" if lever == "In-kind food transfer"
replace lever = "DH - interventions to improve intake/absorption of micronutrients" if lever == "Interventions to improve intake/absorption of micronutrients"
replace lever = "DH - public information campaigns" if lever == "public information campaigns"
replace lever = "FA - school feeding" if lever == "School feeding"
replace lever = "FA - soup kitchen and food pantries" if lever == "Soup kitchen and food pantries"
replace lever = "DH - subsidy" if lever == "subsidy" & segment == "08eating"
replace lever = "Beverage container tax" if lever == "Tax on container"
replace lever = "DH - tax on unhealthy foods" if lever == "Tax on unhealthy foods"

save all_manual.dta, replace

import excel "renaming_dec03.xlsx", sheet("Sheet1") clear
ren A lever
ren B newlev
save renaming_dec03.dta, replace
use all_manual.dta, clear
drop if lever == "Other tax"
merge m:1 lever using renaming_dec03.dta
replace lever = newlev if _merge == 3
drop if _merge == 2
drop _merge newlev
order income_group region_wb fsd_group country segment lever policydecision_details db level covid_mentioned policy_code policy_description, first
save all_manual_dec21.dta, replace

replace lever = "" if lever == "?"
replace segment = "manual" if lever == ""
replace segment = "manual" if segment == "eating? Or food service?"
replace segment = "manual" if segment == "retail and/ or food service - check manually"

// Recoding after manual check
gen isrulesoninputs = 1 if strpos(policydecision_details, "Farm to Fork")
replace lever = "Rules on inputs" if isrulesoninputs == 1 & db == "FAPDA"
replace segment = "01inputs" if isrulesoninputs == 1 & db == "FAPDA"
drop isrulesoninputs
replace lever = "NRM: general conserv management natural resources" if policy_code == 2330
replace lever = "NRM: Water policies and regulations" if policy_code== 2301
replace lever = "NRM: Ecosystem and habitat protection" if policy_code== 2302
replace lever = "NRM forest policies and regulations " if policy_code==2303
replace lever = "NRM: fisheries and aquaculture" if policy_code==2304
replace lever = "NRM: climate change mitigation adaptation" if policy_code== 2305
replace lever = "NRM: renewable energy and energy efficiency" if policy_code == 2306
replace segment = "09multiple" if lever == "labelling"

gen isplanning = 1 if strpos(policydecision_details, "egulation on the growth of fast food")
replace isplanning = 1 if strpos(policydecision_details, "zoning ordinance")
replace lever = "Planning" if isplanning == 1
replace segment = "06retail" if isplanning == 1
drop isplanning

replace segment = "09multiple" if policy_code == 2185
replace lever = "Food safety measures" if policy_code == 2185

replace segment = "09multiple" if policy_code == 2220
replace lever = "Unspecified value chain development measures" if policy_code == 2220

gen islabelling = 1 if policy_description == "Nutrition label standards and regulations on the use of claims and implied claims on food"

replace lever = "Labelling" if islabelling == 1
replace lever = "Labelling" if lever == "labelling"
replace segment = "09multiple" if lever == "Labelling"
drop islabelling

gen framework = 0
replace framework = 1 if segment == "10_frameworks" | strpos(lever, "ramework")
replace segment = "10frameworks" if segment == "10_frameworks"
replace foodwaste = 1 if strpos(lever, "waste")

ren foodwaste reduceFLW

replace segment = "09multiple" if policy_code == 1331 | policy_code == 1332
replace lever = "Food safety measures" if policy_code == 1331 | policy_code == 1332

replace segment = "02farming" if policy_code == 2117
replace lever = "PM: subsidized fuel for prod" if policy_code == 2117

replace segment = "02farming" if policy_code == 2140
replace lever = "PM: unspecified policy for knowledge generation dissemination" if policy_code == 2140

replace segment = "02farming" if policy_code == 2150 | policy_code == 2151
replace lever = "PM: livestock measures and regulations" if policy_code == 2150
replace lever = "PM: fisheries and aquaculture measures and regulations" if policy_code == 2151

replace segment = "02farming" if policy_code == 2221
replace lever = "Data, including national market info system" if policy_code == 2221

replace segment = "02farming" if policy_code == 2303 | policy_code == 2304
replace lever = "NRM: forest policies and regulations" if policy_code == 2303

replace lever = "NRM: land ownership, tenure and titling" if policy_code == 2312

replace segment = "05processing/manuf" if strpos(policy_description, "Improve nutritional quality of the whole")
replace lever = "rules on composition/ reformulation" if strpos(policy_description, "Improve nutritional quality of the whole")

replace lever = "Planning" if policy_description == "Set incentives and rules to create a healthy retail and food service environment" & lever == "? Add stg to retail segment"

replace segment = "07foodservice" if lever == "rules/ standards on provision" & segment == "manual" & strpos(policy_description, "Set incentives and rules to create a healthy retail")

replace lever = "rules on promotion/advertising" if lever == "rules? on promotion/ advertising?"

replace lever = "voluntary regulation" if lever == "voluntary regulation?"

replace lever = "voluntary agreement by companies" if contextoradditionalinfo == "Voluntary commitments to reduce portion sizes"
replace segment = "09multiple" if contextoradditionalinfo == "Voluntary commitments to reduce portion sizes"

replace segment = "07foodservice" if contextoradditionalinfo == "Training for health professionals"
replace lever = "Improving skills/training/knowledge" if contextoradditionalinfo == "Training for health professionals"

replace segment = "09multiple" if contextoradditionalinfo == "Working with food suppliers to provide healthier ingredients"
replace lever = "reformulation" if contextoradditionalinfo == "Working with food suppliers to provide healthier ingredients"
replace lever = "Labelling" if contextoradditionalinfo == "Working with food suppliers to provide healthier ingredients" & country == "United Kingdom"

replace lever = "collaboration" if contextoradditionalinfo == "Governance structures for multi sectoral stakeholder engagement"
replace segment = "09multiple" if contextoradditionalinfo == "Governance structures for multi sectoral stakeholder engagement"

replace lever = "community projects" if contextoradditionalinfo == "Community food production"
replace segment = "08eating" if contextoradditionalinfo == "Community food production"

replace lever = "DH - education" if contextoradditionalinfo == "Initiatives to train school children on growing food"
replace segment = "08eating" if contextoradditionalinfo == "Initiatives to train school children on growing food"

replace lever = "voluntary agreement by companies" if contextoradditionalinfo == "Mandatory limits on level of salt in food products"
replace segment = "09multiple" if contextoradditionalinfo == "Mandatory limits on level of salt in food products"

replace segment = "06retail" if strpos(policydecision_details, "The Special Supplemental Nutrition Program for Women  Infants  and Children  WIC ")

replace segment = "06retail" if strpos(policydecision_details, "Shop Healthy NYC")

replace segment = "06retail" if strpos(policydecision_details, "Local initiatives for healthier foods in stores")

replace segment = "08eating" if strpos(policydecision_details, "Voluntary sugar tax")
replace lever = "DH - tax on unhealthy foods" if strpos(policydecision_details, "Voluntary sugar tax")

save all_manual_feb15.dta, replace

import excel "missing.xlsx", sheet("Sheet1") firstrow clear
save "missing.dta", replace

use all_manual_feb15.dta, clear
append using missing.dta

save all_manual_feb15.dta, replace


// Changes from Jan/Feb 2022

use all_manual_feb15.dta, clear
replace segment="05processing/manuf" if lever=="Framework - value chain devt"
drop if policy_code==1232
drop if lever == "framework policy - territorial devt"
drop if country == "Singapore" & segment == "09multiple" & lever == "reformulation"
drop if lever == "Unspecified value chain development measures" & segment == "09multiple"
replace lever = "Beverage container policy" if lever == "Beverage container deposit refund" | lever == "Beverage container fee" | lever == "Beverage container tax"
replace segment = "09multiple" if lever =="Other - governance/ institutions"
replace lever = "MM: support for farmer/ community mkts" if lever == "MM: value chain - support for farmer/ community mkts"
replace lever = "NRM: fisheries and aquaculture" if lever == "PM: fisheries and aquaculture measures and regulations" 
replace lever = "PM: production subsidy" if lever == "Subsidies (for production)"
replace lever = "Processing and post production facilities" if lever == "Value chain - processing and post production facilities"
replace lever = "rules on promotion/ advertising" if lever == "rules on promotion/advertising"
replace lever = "rules/ standards on provision" if lever == "rules/ standards on provision?"
replace lever = "Rural roads and transport infrastructure" if lever == "Value chain - rural roads and transport infrastructure"
drop if strpos(lever, "voluntary agreement")
drop if lever == "voluntary standards on provision"
replace lever = "NRM: fisheries and aquaculture" if lever == "NRM: fishing quota"
replace segment = "07foodservice" if strpos(policydecision_details, "New London Plan")
replace segment = "07foodservice" if strpos(policydecision_details, "Detroit")
replace lever = "MM: support for farmer/ community mkts" if policy_code == 2224
replace segment = "08eating" if lever == "DH - education"

replace lever = "DH - tax on SSB" if strpos(topics, "Sugary drinks tax")
replace lever = "Import tariff" if lever == "DH - tax on SSB" & segment == "04trade"
replace lever = "DH - dietary guidelines" if strpos(policydecision_details, "Food based dietary guidelines") | strpos(policydecision_details, "Dietary Recommendations") | strpos(policydecision_details, "Estonia uses a food pyramid which has water  physical activity") |  strpos(policydecision_details, "The guidelines for adults have been developed graphically in the form of the Healthy Eating Plate")
replace lever = strtrim(lever)

replace lever = "DH - public information campaigns" if policy_code==1520
replace lever = "DH - dietary guidelines" if strpos(policydecision_details, "dietary guidelines")
replace lever = "Export promotion - improved SPS standards" if policy_code== 3230
replace segment = "01inputs" if lever =="PM: subsidized fuel for prod"
/**/

save "feb17.dta", replace
use "feb17.dta", replace

// creating variables on stated policy - revisions made 12 September 2022

{
gen count = 1
//drop if expired == 1
//drop if covid_mentioned == 1
//NICO - I don't know how to use the blank policies, so I'm simply removing them for now
drop if policydecision_details==""
//
//drop if segment == "10frameworks"
replace segment="02NRM - farming and gen" if lever=="NRM: Ecosystem and habitat protection"
replace segment="02NRM - farming and gen" if lever=="NRM: Water policies and regulations"
replace segment="02NRM - farming and gen" if lever=="NRM: climate change mitigation adaptation"
replace segment="02NRM - farming and gen" if lever=="NRM: conservation and mgmt of natural resources"
replace segment="02NRM - farming and gen" if lever=="NRM: emission rights"
replace segment="02NRM - farming and gen" if lever=="NRM: forest policies and regulations"
replace segment="02NRM - farming and gen" if lever=="NRM: land ownership, tenure and titling"
replace segment="02NRM - farming and gen" if lever=="NRM: land policy"
replace segment="02NRM - farming and gen" if lever=="NRM: renewable energy and energy efficiency"
drop if lever == ""
drop if segment == ""
drop if segment == "manual"
replace segment = "02nfarming" if segment == "02NRM - farming and gen"
replace segment = "03distribution" if segment == "03distribution/transport"
replace segment = "05processing" if segment == "05processing/manuf"
replace segment = "08eating" if lever =="DH - dietary guidelines"
replace lever = "Improving Skills/Training/Knowledge" if lever=="Improving skills/training/knowledge"
replace lever = "Import tariff" if lever=="import tariff"
/**/

// foreach var of varlist(lever){
// gen temp = lower(`var')
// drop if strpos(temp, "framework") 
// drop temp
// }


replace lever = strtrim(lever)

order year policy_code id y_start y_end yearofintroduction, last	
order enddate, last
drop inputs-research_tech	
order policycategory, first
/*
foreach var of varlist(policycategory-coststoprivatepartiestooper){
encode `var', generate(`var'_ds)
}

drop policycategory - coststoprivatepartiestooper
rename *_ds *
*/


gen inclusion = 0



foreach var of varlist(policydecision_details contextoradditionalinfo beneficiaries earmarking budget additionalcommodities policy_description topics lever generaltaxbase segment policycategory policydirection){
gen temp = lower(`var')
replace inclusion = 1 if strpos(temp, "poor") 
replace inclusion = 1 if strpos(temp, "pauvre")
replace inclusion = 1 if strpos(temp, "pobre")
replace inclusion = 1 if strpos(temp, "low income")
replace inclusion = 1 if strpos(temp, "low-income")
replace inclusion = 1 if strpos(temp, "bajos ingresos")
replace inclusion = 1 if strpos(temp, "faible revenu")
replace inclusion = 1 if strpos(temp, "targeted")
replace inclusion = 1 if strpos(temp, "ciblé")
replace inclusion = 1 if strpos(temp, "selectiv")
replace inclusion = 1 if strpos(temp, "livelihood")
replace inclusion = 1 if strpos(temp, "subsistance")
replace inclusion = 1 if strpos(temp, "subsistenc")
replace inclusion = 1 if strpos(temp, "smallholder")
replace inclusion = 1 if strpos(temp, "pequeños agricultores")
replace inclusion = 1 if strpos(temp, "petits exploitants")
replace inclusion = 1 if strpos(temp, "vulnerable")
replace inclusion = 1 if strpos(temp, "vulnérable")
replace inclusion = 1 if strpos(temp, "vulnerable")
replace inclusion = 0 if strpos(temp, "poor health")
replace inclusion = 0 if strpos(temp, "poor diet")
drop temp
}


replace inclusion = 1 if policy_code==1210 /*in-kind food transfer*/
replace inclusion = 1 if policy_code==1211 /*food for work*/
replace inclusion = 1 if policy_code==1212 /*school feeding*/
replace inclusion = 1 if policy_code==1310 /*establishment or modification of food stock*/
replace inclusion = 1 if policy_code==1311 /*release of food stock*/
replace inclusion = 1 if targeted=="Y"

replace inclusion=1 if beneficiaries!=""
/*replace inclusion=0 if beneficiaries!=""*/
replace inclusion=1 if lever=="FA - food coupons"
replace inclusion=1 if lever=="FA - food for work"
replace inclusion=1 if lever=="FA - in kind food transfer"
replace inclusion=1 if lever=="FA - school feeding"
replace inclusion=1 if lever=="FA - soup kitchen and food pantries"
replace inclusion=1 if lever=="FA - subsidy"


tab lever if inclusion==1
tab lever if inclusion==1 & segment!= "10frameworks" & segment != "manual" & iso != "" & segment != "" & covid_mentioned!=1
tab lever if segment!= "10frameworks" & segment != "manual" & iso != "" & segment != "" & covid_mentioned!=1

tab segment if inclusion==1 & segment!= "10frameworks" & segment != "manual" & iso != "" & segment != "" & covid_mentioned!=1
tab segment if segment!= "10frameworks" & segment != "manual" & iso != "" & segment != "" & covid_mentioned!=1


*drop envitarget
*drop temp
gen envitarget = 0

foreach var of varlist(policydecision_details contextoradditionalinfo beneficiaries earmarking budget additionalcommodities policy_description topics lever generaltaxbase segment policycategory policydirection){  
gen temp = lower(`var')
replace envitarget = 1 if strpos(temp, "climate change")

replace envitarget = 1 if strpos(temp, "changement climatique")

replace envitarget = 1 if strpos(temp, "cambio climático")

replace envitarget = 1 if strpos(temp, "environment")

replace envitarget = 1 if strpos(temp, "environnement")

replace envitarget = 1 if strpos(temp, "ambiente")
replace envitarget = 1 if strpos(temp, "greenhouse gas")
replace envitarget = 1 if strpos(temp, "gaz à effet de serre")

replace envitarget = 1 if strpos(temp, "gases de efecto invernadero")
replace envitarget = 1 if strpos(temp, "co2")

replace envitarget = 1 if strpos(temp, "deforestation")
replace envitarget = 1 if strpos(temp, "déforestation")
replace envitarget = 1 if strpos(temp, "deforestación")


replace envitarget = 1 if strpos(temp, "emissions")
replace envitarget = 1 if strpos(temp, "émissions")
replace envitarget = 1 if strpos(temp, "emisiones")
*replace envitarget = 1 if strpos(temp, "sustainab") & strpos(temp, "sustainable development goal") == 0   
*replace envitarget = 1 if strpos(temp, "durable") 
*replace envitarget = 1 if strpos(temp, "sostenible") 
replace envitarget = 1 if strpos(temp, "global warming")
replace envitarget = 1 if strpos(temp, "réchauffement climatique")
replace envitarget = 1 if strpos(temp, "calentamiento global")
replace envitarget = 1 if strpos(temp, "conservation of natur")/*1087*/
replace envitarget = 1 if strpos(temp, "préservation de la nature") 
replace envitarget = 1 if strpos(temp, "conservación de la naturaleza") 
replace envitarget = 1 if strpos(temp, "protection of natur")/*13*/
replace envitarget = 1 if strpos(temp, "protection de la nature")
replace envitarget = 1 if strpos(temp, "protección de la naturaleza")
replace envitarget = 1 if strpos(temp, "ecosystem")/*changed this from ecosystem preserv to ecosystem 828*/
replace envitarget = 1 if strpos(temp, "écosystème") 
replace envitarget = 1 if strpos(temp, "ecosistema") 
replace envitarget = 1 if strpos(temp, "habitat")/*changed from habitat preserv to habitat 195*/
replace envitarget = 1 if strpos(temp, "renewable ener")/*114*/
replace envitarget = 1 if strpos(temp, "énergie renouvelable")
replace envitarget = 1 if strpos(temp, "energía renovable")
/*replace envitarget = 1 if strpos(temp, "green energy") removing this - no results found*/
/*replace envitarget = 1 if strpos(temp, "natural protect") removing this - no results found*/
drop temp
}
sort segment
replace envitarget=1 if segment=="02nfarming"



tab envitarget if framework!=1
tab framework
 


tab envitarget if segment != "manual" & iso != "" & segment != "" & covid_mentioned!= 1 & segment!= "10frameworks"
tab lever if envitarget==1
tab region_wb if envitarget == 1 & segment != "manual" & iso != "" & segment != "" & covid_mentioned!= 1
tab segment if envitarget == 1 & segment != "manual" & iso != "" & segment != "" & covid_mentioned!=1
sort db





gen diethealth = 0 
replace diethealth = 1 if segment=="08eating" & lever=="DH - dietary guidelines"
replace diethealth = 1 if segment=="09multiple" & lever=="Labelling" 
replace diethealth = 1 if segment=="05processing/manuf" & lever=="rules on composition/ reformulation"
replace diethealth = 1 if segment=="07foodservice" & lever=="rules/ standards on provision"
replace diethealth = 1 if segment=="08eating" & lever=="DH - public information campaigns"
replace diethealth = 1 if segment=="08eating" & lever=="DH - education"
replace diethealth = 1 if segment=="06retail" & lever=="rules on promotion/ advertising"
replace diethealth = 1 if segment=="08eating" & lever=="DH - tax on SSB"
replace diethealth = 1 if segment=="08eating" & lever=="DH - interventions to improve intake/absorption of micronutrients"
replace diethealth = 1 if segment=="09multiple" & lever=="collaboration"

replace diethealth = 1 if segment=="08eating" & lever=="DH - breastfeeding promotion"
replace diethealth = 1 if segment=="08eating" & lever=="DH - tax on unhealthy foods"
replace diethealth = 1 if segment=="07foodservice" & lever=="Improving skills/training/knowledge"
replace diethealth = 1 if segment=="07foodservice" & lever=="procurement rules/ standards"
replace diethealth = 1 if segment=="08eating" & lever=="community projects"
replace diethealth = 1 if segment=="06retail" & lever=="Rules/ Standards on Provision (Health/Sustainability)"
replace diethealth = 1 if segment=="07foodservice" & lever=="Planning"

foreach var of varlist(policydecision_details contextoradditionalinfo beneficiaries earmarking budget policy_description topics lever generaltaxbase segment policycategory policydirection commodity1 commodity2 commodity3 additionalcommodities){  
gen temp = lower(`var')
replace diethealth = 1 if strpos(temp, "veg")
replace diethealth = 1 if strpos(temp, "légume")

replace diethealth = 1 if strpos(temp, "fruit")
replace diethealth = 1 if strpos(temp, "fruta")

replace diethealth = 1 if strpos(temp, "diet")
replace diethealth = 1 if strpos(temp, "diète")


replace diethealth = 1 if strpos(temp, "nutrient")
replace diethealth = 1 if strpos(temp, "nutritiv")

replace diethealth = 1 if strpos(temp, "nutrition")
replace diethealth = 1 if strpos(temp, "nutrici")


replace diethealth = 1 if strpos(temp, "healthy food")
replace diethealth = 1 if strpos(temp, "comida sana")
replace diethealth = 1 if strpos(temp, "nourriture saine")


replace diethealth = 1 if strpos(temp, "junk food")
replace diethealth = 1 if strpos(temp, "comida chatarra")

replace diethealth = 1 if strpos(temp, "obese")
replace diethealth = 1 if strpos(temp, "obesity")
replace diethealth = 1 if strpos(temp, "obésité")

replace diethealth = 1 if strpos(temp, "obesidad")
replace diethealth = 1 if strpos(temp, "obes")
replace diethealth = 1 if strpos(temp, "obèse")


replace diethealth = 1 if strpos(temp, "malnutrition")
replace diethealth = 1 if strpos(temp, "desnutrici")

replace diethealth = 1 if strpos(temp, "iron")
replace diethealth = 1 if strpos(temp, "hierro")
replace diethealth = 1 if strpos(temp, "fer")
replace diethealth = 1 if strpos(temp, "vitamin")
drop temp
}

replace diethealth=0 if lever=="FA - food coupons"
replace diethealth=0 if lever=="FA - food for work"
replace diethealth=0 if lever=="FA - in kind food transfer"
replace diethealth=0 if lever=="FA - school feeding"
replace diethealth=0 if lever=="FA - soup kitchen and food pantries"
replace diethealth=0 if lever=="FA - subsidy"

tab diethealth if iso != ""
tab region_wb if diethealth == 1 & iso != ""
tab segment if diethealth == 1 & iso != ""
tab lever if diethealth==1


gen taxonomy=""
replace segment = "01 inputs" if segment=="01inputs"
replace segment = "02 farming" if segment=="02farming"
replace segment = "02 NRM - farming & general" if segment=="02nfarming"
replace segment = "03 distribution & transport" if segment == "03distribution"
replace segment = "04 trade" if segment == "04trade"
replace segment = "05 processing & manufacturing" if segment=="05processing"
replace segment = "06 retail" if segment=="06retail"
replace segment = "07 food service" if segment=="07foodservice"
replace segment = "08 eating" if segment=="08eating"
replace segment = "09 multiple" if segment=="09multiple"


	
replace taxonomy="regulations_certification_standards" if segment =="01 inputs" & lever=="Certification of production inputs"
replace taxonomy="regulations_certification_standards" if segment =="02 farming" & lever=="PM: product certification"
replace taxonomy="direct_food_provision" if segment =="08 eating" & lever=="FA - food coupons"
replace taxonomy="direct_food_provision" if segment =="08 eating" & lever=="FA - food for work"
replace taxonomy="direct_food_provision" if segment =="08 eating" & lever=="FA - in kind food transfer"
replace taxonomy="direct_food_provision" if segment =="08 eating" & lever=="FA - school feeding"
replace taxonomy="direct_food_provision" if segment =="08 eating" & lever=="FA - soup kitchen and food pantries"
replace taxonomy="direct_food_provision" if segment =="08 eating" & lever=="FA - subsidy"
replace taxonomy="direct_food_provision" if segment =="06 retail" & lever=="FA - subsidy"
replace taxonomy="economic_financial" if segment =="02 farming" & lever=="PM: support for ag insurance or risk mgmt"
replace taxonomy="economic_financial" if segment =="02 farming" & lever=="PM: support for finance and credit"
replace taxonomy="economic_financial_trade_related_tax" if segment =="04 trade" & lever=="Import quota"
replace taxonomy="economic_financial_subsidy" if segment =="01 inputs" & lever=="Fertiliser distribution"
replace taxonomy="economic_financial_subsidy" if segment =="01 inputs" & lever=="Fertiliser subsidies/vouchers"
replace taxonomy="economic_financial_subsidy" if segment =="01 inputs" & lever=="Livestock and livestock feed distribution"
replace taxonomy="economic_financial_subsidy" if segment =="01 inputs" & lever=="Machinery support (subsidies or distribution)"
replace taxonomy="economic_financial_subsidy" if segment =="01 inputs" & lever=="PM: subsidized fuel for prod"
replace taxonomy="economic_financial_subsidy" if segment =="01 inputs" & lever=="Seed distribution"
replace taxonomy="economic_financial_subsidy" if segment =="01 inputs" & lever=="Seed subsidies/vouchers"
replace taxonomy="economic_financial_subsidy" if segment =="02 farming" & lever=="PM: production subsidy"
replace taxonomy="economic_financial_tax" if segment =="01 inputs" & lever=="x Exemption, reduction or increase in tax on ag inputs"
replace taxonomy="economic_financial_tax" if segment =="02 farming" & lever=="NRM: tax or fee on ag, fish, for or hunting"
replace taxonomy="economic_financial_tax" if segment =="02 farming" & lever=="PM: farm income or other unspecified ag tax"
replace taxonomy="economic_financial_tax" if segment =="06 retail" & lever=="Beverage container policy"
replace taxonomy="economic_financial_tax" if segment =="08 eating" & lever=="Beverage container policy"
replace taxonomy="economic_financial_tax" if segment =="08 eating" & lever=="DH - tax on SSB"
replace taxonomy="economic_financial_tax" if segment =="08 eating" & lever=="DH - tax on unhealthy foods"
replace taxonomy="economic_financial_tax" if segment =="08 eating" & lever=="VAT on food"
replace taxonomy="economic_financial_trade_related_subsidy" if segment =="04 trade" & lever=="Export subsidy"
replace taxonomy="economic_financial_trade_related_subsidy" if segment =="04 trade" & lever=="Import subsidy"
replace taxonomy="economic_financial_trade_related_tax" if segment =="04 trade" & lever=="Export quota"
replace taxonomy="economic_financial_trade_related_tax" if segment =="04 trade" & lever=="Export tax"
replace taxonomy="economic_financial_trade_related_tax" if segment =="04 trade" & lever=="Import - antidumping duties, countervailing duties, etc"
replace taxonomy="economic_financial_trade_related_tax" if segment =="04 trade" & lever=="Import - tariff-rate quota"
replace taxonomy="economic_financial_trade_related_tax" if segment =="04 trade" & lever=="Import tariff"
replace taxonomy="economic_financial_trade_related_tax" if segment =="04 trade" & lever=="import tariff"
replace taxonomy="governance_organization" if segment =="02 farming" & lever=="collaboration"
replace taxonomy="governance_organization" if segment =="06 retail" & lever=="Collaboration"
replace taxonomy="information_communication" if segment =="02 farming" & lever=="Data, including national market info system"
replace taxonomy="information_communication" if segment =="02 farming" & lever=="PM: knowledge - ag extension and training"
replace taxonomy="information_communication" if segment =="02 farming" & lever=="PM: unspecified policy for knowledge generation dissemination"
replace taxonomy="information_communication" if segment =="02 farming" & lever=="data (collection and application"
replace taxonomy="information_communication" if segment =="06 retail" & lever=="Improving Skills/Training/Knowledge"
replace taxonomy="information_communication" if segment =="07 food service" & lever=="Improving Skills/Training/Knowledge"
replace taxonomy="information_communication" if segment =="08 eating" & lever=="DH - breastfeeding promotion"
replace taxonomy="information_communication" if segment =="08 eating" & lever=="DH - dietary guidelines"
replace taxonomy="information_communication" if segment =="08 eating" & lever=="DH - education"
replace taxonomy="information_communication" if segment =="08 eating" & lever=="DH - public information campaigns"
replace taxonomy="information_communication" if segment =="08 eating" & lever=="data (collection and application"
replace taxonomy="information_communication" if segment =="08 eating" & lever=="improving skills, training, knowledge"
replace taxonomy="market_intervention" if segment =="01 inputs" & lever=="x Market intervention: local input production/provision"
replace taxonomy="market_intervention" if segment =="02 farming" & lever=="MM: agric mkt intervention (eg. price, procurement, etc)"
replace taxonomy="market_intervention" if segment =="02 farming" & lever=="MM: support for farmer/ community mkts"
replace taxonomy="market_intervention" if segment =="02 farming" & lever=="PM: support for cooperatives"
replace taxonomy="market_intervention" if segment =="06 retail" & lever=="price controls"
replace taxonomy="market_intervention_ag_food_stock" if segment =="03 distribution & transport" & lever=="Establishment or modification of food stock"
replace taxonomy="market_intervention_ag_food_stock" if segment =="03 distribution & transport" & lever=="Release of food stock"
replace taxonomy="market_intervention_infrastructure" if segment =="02 farming" & lever=="PM: support to irrigation infrastructure"
replace taxonomy="market_intervention_infrastructure" if segment =="02 farming" & lever=="PM: support to productive assets"
replace taxonomy="market_intervention_infrastructure" if segment =="05 processing & manufacturing" & lever=="Processing and post production facilities"
replace taxonomy="market_intervention_infrastructure" if segment =="03 distribution & transport" & lever=="Rural roads and transport infrastructure"
replace taxonomy="market_intervention_trade" if segment =="04 trade" & lever=="Common market/Economic unions"
replace taxonomy="market_intervention_trade" if segment =="04 trade" & lever=="Customs Union"
replace taxonomy="market_intervention_trade" if segment =="04 trade" & lever=="Other trade-related measures"
replace taxonomy="unspecified_hybrid" if segment =="04 trade" & lever=="Import - other import restrictions"
replace taxonomy="unspecified_hybrid" if segment =="01 inputs" & lever=="seed tech and QAT"
replace taxonomy="unspecified_hybrid" if segment =="01 inputs" & lever=="xx General input measures"
replace taxonomy="unspecified_hybrid" if segment =="02 farming" & lever=="NRM: fisheries and aquaculture"
replace taxonomy="unspecified_hybrid" if segment =="02 farming" & lever=="PM: livestock measures and regulations"
replace taxonomy="unspecified_hybrid" if segment =="02 farming" & lever=="PM: other production support"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: Ecosystem and habitat protection"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: Water policies and regulations"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: climate change mitigation adaptation"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: conservation and mgmt of natural resources"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: emission rights"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: forest policies and regulations"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: land ownership, tenure and titling"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: land policy"
replace taxonomy="unspecified_hybrid" if segment =="02 NRM - farming & general" & lever=="NRM: renewable energy and energy efficiency"
replace taxonomy="unspecified_hybrid" if segment =="04 trade" & lever=="Export - other export promotion measures"
replace taxonomy="unspecified_hybrid" if segment =="04 trade" & lever=="Export - other export restrictions"
replace taxonomy="unspecified_hybrid" if segment =="08 eating" & lever=="DH - interventions to improve intake/absorption of micronutrients"
replace taxonomy="regulations" if segment =="01 inputs" & lever=="Rules on inputs"
replace taxonomy="regulations" if segment =="04 trade" & lever=="Competition policy"
replace taxonomy="regulations" if segment =="04 trade" & lever=="Export ban"
replace taxonomy="regulations" if segment =="04 trade" & lever=="Export promotion - improved SPS standards"
replace taxonomy="regulations" if segment =="04 trade" & lever=="Free or preferential trade agreement"
replace taxonomy="regulations" if segment =="04 trade" & lever=="Government procurement through imports"
replace taxonomy="regulations" if segment =="04 trade" & lever=="Import - non tariff barrier - sanitary phytosanitary measures (SPS)"
replace taxonomy="regulations" if segment =="04 trade" & lever=="Import ban"
replace taxonomy="regulations" if segment =="05 processing & manufacturing" & lever=="rules on composition/ reformulation"
replace taxonomy="regulations" if segment =="06 retail" & lever=="Rules/ Standards on Provision (Health/Sustainability)"
replace taxonomy="regulations" if segment =="06 retail" & lever=="rules on promotion/ advertising"
replace taxonomy="regulations" if segment =="07 food service" & lever=="Planning"
replace taxonomy="regulations" if segment =="07 food service" & lever=="procurement rules/ standards"
replace taxonomy="regulations" if segment =="07 food service" & lever=="rules/ standards on provision"
replace taxonomy="regulations" if segment =="08 eating" & lever=="Rules on Promotion/Advertising"
replace taxonomy="regulations_certification_standards" if segment =="02 farming" & lever=="PM: standards: food safety/ quality/ traceability"
replace taxonomy="regulations_certification_standards" if segment =="04 trade" & lever=="Import - non tariff barrier - technical barriers to trade"
replace taxonomy="market_intervention_trade" if segment =="04 trade" & lever=="Trade facilitation"
replace taxonomy="technology_innovation" if segment =="02 farming" & lever=="PM: knowledge - ag research and tech"
replace taxonomy="technology_innovation" if segment =="02 farming" & lever=="community projects: agriculture"
replace taxonomy="technology_innovation" if segment =="08 eating" & lever=="Technology/ Innovation"
replace taxonomy="technology_innovation" if segment =="08 eating" & lever=="community projects"
replace taxonomy="governance_organization" if segment =="09 multiple" & lever=="collaboration"
replace taxonomy="unspecified_hybrid" if segment =="09 multiple" & lever=="Food safety measures"
replace taxonomy="regulations" if segment =="09 multiple" & lever=="Labelling"
replace taxonomy="governance_organization" if segment =="09 multiple" & lever=="Other - governance/ institutions"
replace taxonomy="governance_organization" if segment =="09 multiple" & lever=="Other - governance/ institutions"

replace segment = "01Inputs" if segment=="01 inputs"
replace segment = "02Farming" if segment=="02 farming"
replace segment = "10Natural_resource_mgmt" if segment=="02 NRM - farming & general"
replace segment = "03Distribution_transport" if segment == "03 distribution & transport"
replace segment = "04Trade" if segment == "04 trade"
replace segment = "05Processing_manufacturing" if segment=="05 processing & manufacturing"
replace segment = "06Retail" if segment=="06 retail"
replace segment = "07Foodservice" if segment=="07 food service"
replace segment = "08Eating" if segment=="08 eating"
replace segment = "09Multiple" if segment=="09 multiple"
}


//creating defn, etc 12 Sept 2022

{ 
gen defn="."
gen itype="."



replace defn = "public information campaigns on the importance of breastfeeding" if segment=="08Eating" & lever=="DH - breastfeeding promotion"
replace defn = "	the establishment of recommended amounts and proportions of different types of foods to be consumed for a healthy diet." if segment=="08Eating" & lever=="DH - dietary guidelines"
replace defn = "	training of health care providers on nutrition; school curriculum incorporating nutrition" if segment=="08Eating" & lever=="DH - education"
replace defn = "media campaigns and other type of outreach to promote changes in food consumption - eg. fruit and vegetable consumption, consumption of fewer calories or following food based dietary guidelines." if segment=="08Eating" & lever=="DH - public information campaigns"
replace defn = "	collection and use of data on consumer eating" if segment=="08Eating" & lever=="Data (collection and application)"
replace defn = "	efforts to improve knowledge and skills of individuals regarding healthy and/ or sustainable eating" if segment=="08Eating" & lever=="Improving skills, training, knowledge"
replace defn = "	release of food stock to help stabilize domestic prices or to distribute food to the poor and vulnerable" if segment=="03Distribution_transport" & lever=="Release of food stock"
replace defn = "	control of prices on basic foods to prevent prohibitively expensive sales; these may be a price ceiling, price floor or fixed price" if segment=="06Retail" & lever=="price controls"
replace defn = "	support for food retail (often healthy foods) in remote areas" if segment=="06Retail" & lever=="Direct Food Assistance (Retail Support)"
replace defn = "	projects engaging a community in various activities to improve nutrition or environmental outcomes; these may include gardening, food sharing to reduce food waste, learning to cook, etc" if segment=="08Eating" & lever=="community projects"
replace defn = "	government provided food stamps, ration cards or vouchers that may be exchanged for food in certain stores." if segment=="08Eating" & lever=="FA - food coupons"
replace defn = "	food distributed to recipients conditional upon their performing work" if segment=="08Eating" & lever=="FA - food for work"
replace defn = "unconditional distribution of in kind food" if segment=="08Eating" & lever=="FA - in kind food transfer"
replace defn = "children provided with food at school or to take home given their attendance in classes" if segment=="08Eating" & lever=="FA - school feeding"
replace defn = "distribution of prepared food or food supplies to low income and homeless people" if segment=="08Eating" & lever=="FA - soup kitchen and food pantries"
replace defn = "lowered price of specific foods normally targeting vulnerable populations" if segment=="08Eating" & lever=="FA - subsidy"
replace defn = "	application of technology to consumer eating " if segment=="08Eating" & lever=="Technology/ Innovation	"
replace defn = "	establishment of multisectoral government bodies that aim to improve nutrition	" if segment=="09Multiple" & lever=="collaboration"
replace defn = "	program or plan to promote agricultural and rural development" if segment=="02Farming" & lever=="framework - ag rural devt general"
replace defn = "	program or plan to promote crop development and diversification" if segment=="02Farming" & lever=="framework - crop devt and diversification"
replace defn = "	program or plan to promote sustainable and healthy fisheries" if segment=="02Farming" & lever=="framework - fisheries"
replace defn = "	program or plan to promote livestock production " if segment=="02Farming" & lever=="framework - livestock"
replace defn = "	program or plan to promote forestry " if segment=="02Farming" & lever=="Framework - forestry	"
replace defn = "	program or plan to promote and diversify exports" if segment=="04Trade" & lever=="framework - export promotion and diversification"
replace defn = "	program or plan to promote trade generally" if segment=="04Trade" & lever=="framework - trade (general)"
replace defn = "	program or plan to encourage the industrialization of the economy, including the increase in value added to agricultural production through processing" if segment=="05Processing_manufacturing" & lever=="Framework - value chain development"
replace defn = "	program or plan targeting food processors to achieve a certain goal" if segment=="05Processing_manufacturing" & lever=="Framework Policy: Processing/Manufacturing Sector"
replace defn = "	program or plan to increase value addition to agricultural production" if segment=="05Processing_manufacturing" & lever=="Framework - value chain devt"
replace defn = "program or plan targeting food retailers to achieve a certain goal" if segment=="06Retail" & lever=="Framework policy - retail"
replace defn = "	program or plan targeting restaurants and other food service providers to improve food culture	" if segment=="07Foodservice" & lever=="Framework Policy: Food Culture"
replace defn = "	program or plan targeting food service providers to achieve a certain goal" if segment=="07Foodservice" & lever=="Framework Policy: Food Service Sector"
replace defn = "program or plan to reduce food loss and waste" if segment=="09Multiple" & lever=="Framework - food loss and waste"
replace defn = "program or plan to improve food safety " if segment=="09Multiple" & lever=="Framework - food safety"
replace defn = "program or plan to improve food security and nutrition" if segment=="09Multiple" & lever=="Framework - FSN"
replace defn = "program or plan to improve nutrition" if segment=="09Multiple" & lever=="Framework - Nutrition"
replace defn = "	broad program or plan addressing labor and employment in the economy as a whole (not specific to agriculture)" if segment=="11General_framework" & lever=="Framework - gen - labor and employment"
replace defn = "broad program or plan addressing social protection and support for the vulnerable in the economy as a whole (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - gen - social protection"
replace defn = "	broad program or plan addressing youth development in the economy as a whole (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - gen - youth development"
replace defn = "broad program or plan addressing biodiversity in the economy as a whole (not specific to agriculture)" if segment=="11General_framework" & lever=="Framework - NR - biodiversity"
replace defn = "	broad program or plan addressing climate change and the economy as a whole (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - NR - climate change"
replace defn = "	broad plan for addressing forestry management" if segment=="11General_framework" & lever=="Framework - NR - forestry"
replace defn = "	broad program or plan addressing natural resources in the economy as a whole (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - NR - general	"
replace defn = "	broad program or plan addressing land use, land policy and management (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - NR - land"
replace defn = "	broad program or plan addressing the usage and management of water resources (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - NR - water resources"
replace defn = "	broad program or plan addressing socio economic investment (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - Soc Econ investment plan"
replace defn = "	broad program or plan addressing socio economic investment over the long term (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - Soc Econ LT devt plan/ vision"
replace defn = "	broad program or plan addressing how to implement medium term socio economic investment plans (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - Soc Econ MT implementation strategy"
replace defn = "	broad program or plan addressing poverty reduction through the economy as a whole (not specific to agriculture)	" if segment=="11General_framework" & lever=="Framework - Soc Econ poverty reduction"
replace defn = "	various types of interventions aimed at improving micronutrient consumption	" if segment=="08Eating" & lever=="DH - interventions to improve intake/absorption of micronutrients"
replace defn = "	distribution of fertiliser (domestically or internationally produced) to farmers	" if segment=="01Inputs" & lever=="Fertiliser distribution"
replace defn = "	farmers offered a subsidized price on fertiliser or voucher for fertiliser" if segment=="01Inputs" & lever=="Fertiliser subsidies/vouchers"
replace defn = "	distribution of free or discounted livestock and livestock feed to farmers	" if segment=="01Inputs" & lever=="Livestock and livestock feed distribution"
replace defn = "	discounted or free farming machinery sold/ distributed to farmers	" if segment=="01Inputs" & lever=="Machinery support (subsidies or distribution)"
replace defn = "	distribution of free seed to farmers	" if segment=="01Inputs" & lever=="Seed distribution"
replace defn = "	distribution of discounted seed or vouchers for seed to farmers	" if segment=="01Inputs" & lever=="Seed subsidies/vouchers"
replace defn = "	measures related to seed production, quality assurance  and certification	" if segment=="01Inputs" & lever=="seed tech and QAT"
replace defn = "	a change in taxes on inputs to agricultural production 	" if segment=="01Inputs" & lever=="x Exemption, reduction or increase in tax on ag inputs"
replace defn = "	measures aiming to encourage the local production of fertiliser and other inputs	" if segment=="01Inputs" & lever=="x Market intervention: local input production/provision	"
replace defn = "	other input related measures	" if segment=="01Inputs" & lever=="xx General input measures"
replace defn = "	the certification of production inputs as being organic or satisfying another criteria	" if segment=="01Inputs" & lever=="Certification of production inputs"
replace defn = "	programme or plan to manage agricultural inputs" if segment=="01Inputs" & lever=="Framework policy - agricultural inputs"
replace defn = "	measures to collect and disseminate information about the agricultural sector	" if segment=="02Farming" & lever=="Data, including national market info system"
replace defn = "	government intervention in the market by such measures as procuring agricultural products or setting prices on particular crops	" if segment=="02Farming" & lever=="MM: agric mkt intervention (eg. price, procurement, etc)"
replace defn = "	measures aimed at facilitating farmers' direct sales to the public through farmer's markets or other means	" if segment=="02Farming" & lever=="MM: support for farmer/ community mkts"
replace defn = "	measures aimed at conserving fisheries and aquaculture	" if segment=="02Farming" & lever=="NRM: fisheries and aquaculture"
replace defn = "	measures aimed at improving farmers' access to private or public technical training	" if segment=="02Farming" & lever=="PM: knowledge - ag extension and training"
replace defn = "	developing and promoting agricultural research on various topics including plant breeding, ecology and disease control among plants and animals." if segment=="02Farming" & lever=="PM: knowledge - ag research and tech"
replace defn = "	measures related to livestock that are not classified under other categories such as livestock and feed distribution or insurance	" if segment=="02Farming" & lever=="PM: livestock measures and regulations"
replace defn = "	additional support to production that may not be classified according to any of the other categories in production measures	" if segment=="02Farming" & lever=="PM: other production support"
replace defn = "	certification of agricultural production methods as satisfying criteria needed to be considered organic or fulfilling another criteria	" if segment=="02Farming" & lever=="PM: product certification"
replace defn = "	payments based upon farm output or area to support farm production and income generally	" if segment=="02Farming" & lever=="PM: production subsidy"
replace defn = "	payment or reduced tax for more sustainable agricultural production practices (includes fisheries and forestry)	" if segment=="02Farming" & lever=="NRM: subsidy for more sustainable production"
replace defn = "	measures aimed at improving plant and animal genetic resources as well as sanitary measures	" if segment=="02Farming" & lever=="PM: standards: food safety/ quality/ traceability"
replace defn = "	measures to limit risk in agricultural production, including derivative contracts to help mitigate price risk, insurance instruments (index-based crop insurance, livestock insurance and reinsurance) and catastrophe bonds.	" if segment=="02Farming" & lever=="PM: support for ag insurance or risk mgmt"
replace defn = "	institutional support for producer's organizations	" if segment=="02Farming" & lever=="PM: support for cooperatives"
replace defn = "	measures to improve access to credit by smallholder farmers either by changing eligibility requirements in private banks, constructing more bank branches in rural areas or making public funds available to farmers. " if segment=="02Farming" & lever=="PM: support for finance and credit"
replace defn = "	measures to develop or refurbish irrigation infrastructure 	" if segment=="02Farming" & lever=="PM: support to irrigation infrastructure"
replace defn = "	measures to improve machinery, livestock or crop infrastructure at the farm or producer organization level	" if segment=="02Farming" & lever=="PM: support to productive assets"
replace defn = "	measures other than research or agricultural extension that are intended to develop and disseminate knowledge related to agriculture	" if segment=="02Farming" & lever=="PM: unspecified policy for knowledge generation and dissemination"
replace defn = "	networks of farmers and other stakeholders united to achieve a goal related to agricultural production	" if segment=="02Farming" & lever=="Collaboration"
replace defn = "	community based projects that are centered around agricutural production activities	" if segment=="02Farming" & lever=="Community projects: agriculture"
replace defn = "	subsidies on fuel or free fuel for use in agricultural production	" if segment=="02Farming" & lever=="PM: subsidized fuel for production"
replace defn = "	measures to create or change (increase or decrease amounts held) food stock, such as grain reserves	" if segment=="03Distribution_transport" & lever=="Establishment or modification of food stock"
replace defn = "	government purchasing and storing agricultural production in order to stabilize prices  or create distribution systems for direct food assistance	" if segment=="03Distribution_transport" & lever=="Agricultural market  intervention (purchase and storage of food)"
replace defn = "	interventions to train food producers on sustainable food production methods	" if segment=="05Processing_manufacturing" & lever=="Improving Skills/Training/Knowledge"
replace defn = "	networks of processors and other stakeholders united to achieve a goal related to food processing	" if segment=="05Processing_manufacturing" & lever=="Collaboration"
replace defn = "	collection and use of data relative to food processing	" if segment=="05Processing_manufacturing" & lever=="Data (Collection and Application)"
replace defn = "	the application of technology to food processing (eg. development of meat substitutes)	" if segment=="05Processing_manufacturing" & lever=="Technology/ Innovation	"
replace defn = "	networks of retailers and other stakeholders united to achieve a goal related to health or the environment	" if segment=="06Retail" & lever=="Collaboration"
replace defn = "	collection and application of data on food retail sales and purchases	" if segment=="06Retail" & lever=="Data (Collection and Application)"
replace defn = "	support for financing retail outlets (often healthy foods)  in underserved areas	" if segment=="06Retail" & lever=="Finance/Investment/Insurance (Support for)"
replace defn = "	interventions to train food retailers on healthy and  sustainable foods 	" if segment=="06Retail" & lever=="Improving Skills/Training/Knowledge"
replace defn = "	financial support to retailers that support healthier food options	" if segment=="06Retail" & lever=="Incentives for Improving Provision"
replace defn = "	application of technology to retail to improve sales, sustainability and health	" if segment=="06Retail" & lever=="Technology and Innovation"
replace defn = "	training of those in food service on nutrition and/ or environmental issues 	" if segment=="07Foodservice" & lever=="Improving skills/Training/Knowledge"
replace defn = "	interventions to provide skills and training to staff working  in food service	" if segment=="07Foodservice" & lever=="Improving Skills/Training/Knowledge"
replace defn = "	financial incentives to encourage provision of healthier foods in food service.	" if segment=="07Foodservice" & lever=="Incentivising Improved Provision"
replace defn = "	networks of food service operators  united to achieve a goal related to health or the environment	" if segment=="07Foodservice" & lever=="Collaboration"
replace defn = "	collection and application of data on food service	" if segment=="07Foodservice" & lever=="Data (Collection and Application)"
replace defn = "	applying technology to food service in order to achieve goals such as sustainability, health or sales	" if segment=="07Foodservice" & lever=="Technology/ Innovation"
replace defn = "	measure to support governance of agricultural systems	" if segment=="09Multiple" & lever=="Other - governance/ institutions"
replace defn = "	standardized ways of reporting nutritional contents, sustainability impacts of foods; measures may be implemented in the processing and manufacturing, retail or food services segment. 	" if segment=="09Multiple" & lever=="Labelling"
replace defn = "	measures aimed at reducing risks of climate change	" if segment=="10Natural_resource_mgmt" & lever=="NRM: climate change mitigation adaptation"
replace defn = "	measures aimed at conserving natural resources which are not specific to ecosystem/ habitat preservation, emission rights, fisheries and aquaculture, forestry, land, renewable energy and energy efficiency. 	" if segment=="10Natural_resource_mgmt" & lever=="NRM: conservation and mgmt of natural resources"
replace defn = "	measures aimed at preserving ecosystems and habitats	" if segment=="10Natural_resource_mgmt" & lever=="NRM: Ecosystem and habitat protection"
replace defn = "	allowances for farmers to emit specified amounts of greenhouse gases	" if segment=="10Natural_resource_mgmt" & lever=="NRM: emission rights"
replace defn = "	measures intending to conserve and maintain forest resources	" if segment=="10Natural_resource_mgmt" & lever=="NRM: forest policies and regulations"
replace defn = "	measures intended to encourage the use of renewable energy and reduce overall energy consumption	" if segment=="10Natural_resource_mgmt" & lever=="NRM: renewable energy and energy efficiency"
replace defn = "	construction or maintenance of transport infrastructure, including rural roads	" if segment=="03Distribution_transport" & lever=="Rural roads and transport infrastructure"
replace defn = "	construction of rice mills or other processing facilities.	" if segment=="05Processing_manufacturing" & lever=="Processing and post production facilities"
replace defn = "	rules on food packaging often in an effort to achieve safety or environmental goals	" if segment=="03Distribution_transport" & lever=="Rules on food packaging"
replace defn = "	safety or quality standards for distribution and transport and/ or the traceability of such products	" if segment=="03Distribution_transport" & lever=="Standards: safety/ quality/ traceability"
replace defn = "	measures to discourage excessive market power by individual companies	" if segment=="04Trade" & lever=="Competition policy"
replace defn = "	food fortification at the point of processing or limitations on certain ingredients used by manufacturers.	" if segment=="05Processing_manufacturing" & lever=="rules on composition/ reformulation"
replace defn = "	restrictions on the advertising of certain foods as well as limitations on brand sponsorship	" if segment=="05Processing_manufacturing" & lever=="Rules on Promotion/Advertising"
replace defn = "	certification of production methods such as fair trade	" if segment=="05Processing_manufacturing" & lever=="Certification of Production Methods/Products"
replace defn = "	safety or quality standards applied to food processing and/ or tracing of produce through the processing phase	" if segment=="05Processing_manufacturing" & lever=="Standards: Safety/Quality/Traceability"
replace defn = "	zoning laws  to increase the availability of retail outlets selling more healthy foods in underserved areas	" if segment=="06Retail" & lever=="Planning"
replace defn = "	restrictions on food advertising and other forms of commercial promotion	" if segment=="06Retail" & lever=="rules on promotion/ advertising	"
replace defn = "	rules to encourage sales of healthier foods in retail outlets	" if segment=="06Retail" & lever=="Rules/ standards on provision"
replace defn = "	certification of products sold in retail spaces as being fair trade, organic or satisfying other criteria	" if segment=="06Retail" & lever=="Certification of Production Methods/Products"
replace defn = "	safety or quality standards applied to foods sold in retail outlets	" if segment=="06Retail" & lever=="Standards: Safety/Quality/Traceability"
replace defn = "	rules regarding what foods may be served in institutions affiliated with the government	" if segment=="07Foodservice" & lever=="procurement rules/ standards"
replace defn = "	rules on what foods may be served in government affiliated institutions and schools	" if segment=="07Foodservice" & lever=="rules/ standards on provision"
replace defn = "	planning and zoning laws designed to limit certain types of food service (eg. fast food)	" if segment=="07Foodservice" & lever=="Planning"
replace defn = "	certification of particular production methods and products used in food service	" if segment=="07Foodservice" & lever=="Certification of Production Methods/Products"
replace defn = "	limitations on certain ingredients in food products	" if segment=="07Foodservice" & lever=="Composition/Reformulation (Food)"
replace defn = "	restrictions on advertising and other forms of commercial promotion by the food service industry	" if segment=="07Foodservice" & lever=="Rules on Promotion/Advertising "
replace defn = "	safety or quality standards applied to the food service industry	" if segment=="07Foodservice" & lever=="Standards: Safety/Quality/Traceability"
replace defn = "	restrictions on advertising and brand sponsorship by particular foods.	" if segment=="08Eating" & lever=="Rules on Promotion/Advertising"
replace defn = "	measures to avoid food safety hazards through food labelling, practices related to food additives and policies in the manufacturing, processing and certification of foods	" if segment=="09Multiple" & lever=="Food safety measures"
replace defn = "	policies regarding the security of land tenure	" if segment=="10Natural_resource_mgmt" & lever=="NRM: land ownership, tenure and titling	"
replace defn = "	other policies related to land including land use planning and land management	" if segment=="10Natural_resource_mgmt" & lever=="NRM: land policy"
replace defn = "	measures to conserve and manage the use of water	" if segment=="10Natural_resource_mgmt" & lever=="NRM: Water policies and regulations"
replace defn = "	tax, fee or deposit refund on beverage containers; the majority are implemented at consumer rather than producer level  	" if segment=="06Retail" & lever=="Beverage container policy"
replace defn = "	tax on unhealthy foods in addition to or rather than SSB; foods may include those high in fat or salt content; may include high sugar content foods in addition to SSB; may be implemented at consumer or producer level	" if segment=="08Eating" & lever=="DH - tax on unhealthy foods	"
replace defn = "	tax on sugar sweetened beverages only (no tax on other types of foods); may be implemented at consumer or producer level	" if segment=="08Eating" & lever=="DH - tax on SSB"
replace defn = "	tax, fee or deposit refund on beverage containers; the majority are implemented at consumer rather than producer level  	" if segment=="08Eating" & lever=="Beverage container policy"
replace defn = "	a tax on food sales at retail level (check this)	" if segment=="08Eating" & lever=="VAT on food"
replace defn = "	taxes or fees for using various natural resources	" if segment=="02Farming" & lever=="NRM: tax or fee on ag, fish, for or hunting"
replace defn = "	a change in the tax rate on farm income or agricultural production	" if segment=="02Farming" & lever=="PM: farm income or other unspecified ag tax"
replace defn = "	fiscal measures relative to particular ingredients such as sugar	" if segment=="05Processing_manufacturing" & lever=="Taxes"
replace defn = "	application of fiscal measures to encourage the use of ingredients or the serving of particular foods	" if segment=="07Foodservice" & lever=="Tax on processor"
replace defn = "	in addition to customs union these have liberalized movement of capital and people and/ or harmonized domestic policies	" if segment=="04Trade" & lever=="Common market/Economic unions"
replace defn = "	agreement among countries regarding free trade of certain products within the union and agree to a common external tariff for imports from countries outside of the union	" if segment=="04Trade" & lever=="Customs Union"
replace defn = "	other measures to promote exports; these may include establishing industrial parks. 	" if segment=="04Trade" & lever=="Export - other export promotion measures"
replace defn = "	measure other than those classified elsewhere and meant to restrict exports. This may include licensing to have the rights for export.	" if segment=="04Trade" & lever=="Export - other export restrictions"
replace defn = "	certain products forbidden from being exported.	" if segment=="04Trade" & lever=="Export ban"
replace defn = "		" if segment=="04Trade" & lever=="Export promotion - improved SPS standards"
replace defn = "	establishment of a limit on the amount of a product that may be exported within a given time frame. 	" if segment=="04Trade" & lever=="Export quota"
replace defn = "	subsidy to encourage exports of certain goods	" if segment=="04Trade" & lever=="Export subsidy"
replace defn = "	tax on exported goods	" if segment=="04Trade" & lever=="Export tax"
replace defn = "	establishment of a bilateral or multilateral agreement on terms of trade such as reducing or eliminating import tariffs.	" if segment=="04Trade" & lever=="Free or preferential trade agreement"
replace defn = "	grains for stocks and other goods imported by the government 	" if segment=="04Trade" & lever=="Government procurement through imports"
replace defn = "	tariffs assessed on imports that have been subsidized by the government of the exporter and are thought to disrupt the importing country's market.	" if segment=="04Trade" & lever=="Import - antidumping duties, countervailing duties, etc"
replace defn = "	government interventions to safeguard the health of the population, plants and animals from the risks of imported goods.	" if segment=="04Trade" & lever=="Import - non tariff barrier - sanitary phytosanitary measures (SPS)"
replace defn = "	regulations and standards with respect to labeling or certification that are required of  imported products	" if segment=="04Trade" & lever=="Import - non tariff barrier - technical barriers to trade"
replace defn = "	import restrictions other than those categorized here.	" if segment=="04Trade" & lever=="Import - other import restrictions"
replace defn = "	import restriction that combine tariff and quotas. Imports entering a country within the quota are taxed at a lower rate than those entering the country after the quota has been reached.	" if segment=="04Trade" & lever=="Import - tariff-rate quota"
replace defn = "	measure to forbid the importation of a specific good.	" if segment=="04Trade" & lever=="Import ban"
replace defn = "	a restriction on the amount of a given item that can be imported in a certain time period. Import licenses are often sold or administered to individuals to help administer this.	" if segment=="04Trade" & lever=="Import quota"
replace defn = "	subsidy on imported good(s). 	" if segment=="04Trade" & lever=="Import subsidy"
replace defn = "	tariff or duty assessed on imported good(s).	" if segment=="04Trade" & lever=="Import tariff"
replace defn = "	trade related measure that does not fit in any of the other categories provided.	" if segment=="04Trade" & lever=="Other trade-related measures"
replace defn = "	measures to facilitate the movement of goods such as by simplifying customs procedures.	" if segment=="04Trade" & lever=="Trade facilitation"
replace defn = "	support to producers for achieving SPS standards needed for export	" if segment=="04Trade" & lever=="Export promotion - improved SPS standards"		

replace itype = "	Behavioral	" if segment=="08Eating" & lever=="DH - breastfeeding promotion"
replace itype = "	Behavioral	" if segment=="08Eating" & lever=="DH - dietary guidelines"
replace itype = "	Behavioral	" if segment=="08Eating" & lever=="DH - education"
replace itype = "	Behavioral	" if segment=="08Eating" & lever=="DH - public information campaigns"
replace itype = "	Behavioral	" if segment=="08Eating" & lever=="Data (collection and application)"
replace itype = "	Behavioral	" if segment=="08Eating" & lever=="Improving skills, training, knowledge"
replace itype = "	Consumer subsidy	" if segment=="03Distribution_transport" & lever=="Release of food stock"
replace itype = "	Consumer subsidy	" if segment=="06Retail" & lever=="price controls"
replace itype = "	Consumer subsidy	" if segment=="06Retail" & lever=="Direct Food Assistance (Retail Support)"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="community projects"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="FA - food coupons"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="FA - food for work"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="FA - in kind food transfer"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="FA - school feeding"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="FA - soup kitchen and food pantries"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="FA - subsidy"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="Technology/ Innovation"
replace itype = "	Consumer subsidy	" if segment=="09Multiple" & lever=="collaboration"
replace itype = "	NA	" if segment=="02Farming" & lever=="framework - ag rural devt general"
replace itype = "	NA	" if segment=="02Farming" & lever=="framework - crop devt and diversification"
replace itype = "	NA	" if segment=="02Farming" & lever=="framework - fisheries"
replace itype = "	NA	" if segment=="02Farming" & lever=="framework - livestock"
replace itype = "	NA	" if segment=="02Farming" & lever=="Framework - forestry"
replace itype = "	NA	" if segment=="04Trade" & lever=="framework - export promotion and diversification"
replace itype = "	NA	" if segment=="04Trade" & lever=="framework - trade (general)"
replace itype = "	NA	" if segment=="05Processing_manufacturing" & lever=="Framework - value chain development"
replace itype = "	NA	" if segment=="05Processing_manufacturing" & lever=="Framework Policy: Processing/Manufacturing Sector"
replace itype = "	NA	" if segment=="05Processing_manufacturing" & lever=="Framework - value chain devt"
replace itype = "	NA	" if segment=="06Retail" & lever=="Framework policy - retail"
replace itype = "	NA	" if segment=="07Foodservice" & lever=="Framework Policy: Food Culture"
replace itype = "	NA	" if segment=="07Foodservice" & lever=="Framework Policy: Food Service Sector"
replace itype = "	NA	" if segment=="09Multiple" & lever=="Framework - food loss and waste"
replace itype = "	NA	" if segment=="09Multiple" & lever=="Framework - food safety"
replace itype = "	NA	" if segment=="09Multiple" & lever=="Framework - FSN"
replace itype = "	NA	" if segment=="09Multiple" & lever=="Framework - Nutrition"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - gen - labor and employment"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - gen - social protection"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - gen - youth development"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - NR - biodiversity"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - NR - climate change"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - NR - forestry"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - NR - general"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - NR - land"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - NR - water resources"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - Soc Econ investment plan"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - Soc Econ LT devt plan/ vision"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - Soc Econ MT implementation strategy"
replace itype = "	NA	" if segment=="11General_framework" & lever=="Framework - Soc Econ poverty reduction"
replace itype = "	Consumer subsidy	" if segment=="08Eating" & lever=="DH - interventions to improve intake/absorption of micronutrients"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Fertiliser distribution"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Fertiliser subsidies/vouchers"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Livestock and livestock feed distribution"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Machinery support (subsidies or distribution)"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Seed distribution"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Seed subsidies/vouchers"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="seed tech and QAT"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="x Exemption, reduction or increase in tax on ag inputs"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="x Market intervention: local input production/provision"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="xx General input measures"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Certification of production inputs"
replace itype = "Producer subsidy" if segment=="01Inputs" & lever=="Framework policy - agricultural inputs"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="Data, including national market info system"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="MM: agric mkt intervention (eg. price, procurement, etc)"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="MM: support for farmer/ community mkts"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="NRM: fisheries and aquaculture"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: knowledge - ag extension and training"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: knowledge - ag research and tech"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: livestock measures and regulations"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: other production support"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: product certification"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: production subsidy"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="NRM: subsidy for more sustainable production"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: standards: food safety/ quality/ traceability"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: support for ag insurance or risk mgmt"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: support for cooperatives"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: support for finance and credit"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: support to irrigation infrastructure"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: support to productive assets"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: unspecified policy for knowledge generation and dissemination"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="Collaboration"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="Community projects: agriculture"
replace itype = "Producer subsidy" if segment=="02Farming" & lever=="PM: subsidized fuel for production"
replace itype = "Producer subsidy" if segment=="03Distribution_transport" & lever=="Establishment or modification of food stock"
replace itype = "Producer subsidy" if segment=="03Distribution_transport" & lever=="Agricultural market  intervention (purchase and storage of food)"
replace itype = "Producer subsidy" if segment=="05Processing_manufacturing" & lever=="Improving Skills/Training/Knowledge"
replace itype = "Producer subsidy" if segment=="05Processing_manufacturing" & lever=="Collaboration"
replace itype = "Producer subsidy" if segment=="05Processing_manufacturing" & lever=="Data (Collection and Application)"
replace itype = "Producer subsidy" if segment=="05Processing_manufacturing" & lever=="Technology/ Innovation"
replace itype = "Producer subsidy" if segment=="06Retail" & lever=="Collaboration"
replace itype = "Producer subsidy" if segment=="06Retail" & lever=="Data (Collection and Application)"
replace itype = "Producer subsidy" if segment=="06Retail" & lever=="Finance/Investment/Insurance (Support for)"
replace itype = "Producer subsidy" if segment=="06Retail" & lever=="Improving Skills/Training/Knowledge"
replace itype = "Producer subsidy" if segment=="06Retail" & lever=="Incentives for Improving Provision"
replace itype = "Producer subsidy" if segment=="06Retail" & lever=="Technology and Innovation"
replace itype = "Producer subsidy" if segment=="07Foodservice" & lever=="Improving Skills/Training/Knowledge"
replace itype = "Producer subsidy" if segment=="07Foodservice" & lever=="Improving Skills/Training/Knowledge"
replace itype = "Producer subsidy" if segment=="07Foodservice" & lever=="Incentivising Improved Provision"
replace itype = "Producer subsidy" if segment=="07Foodservice" & lever=="Collaboration"
replace itype = "Producer subsidy" if segment=="07Foodservice" & lever=="Data (Collection and Application)"
replace itype = "Producer subsidy" if segment=="07Foodservice" & lever=="Technology/ Innovation"
replace itype = "Producer subsidy" if segment=="09Multiple" & lever=="Other - governance/ institutions"
replace itype = "Producer subsidy" if segment=="09Multiple" & lever=="Labelling"
replace itype = "Producer subsidy" if segment=="10Natural_resource_mgmt" & lever=="NRM: climate change mitigation adaptation"
replace itype = "Producer subsidy" if segment=="10Natural_resource_mgmt" & lever=="NRM: conservation and mgmt of natural resources"
replace itype = "Producer subsidy" if segment=="10Natural_resource_mgmt" & lever=="NRM: Ecosystem and habitat protection"
replace itype = "Tax on producer" if segment=="10Natural_resource_mgmt" & lever=="NRM: emission rights"
replace itype = "Producer subsidy" if segment=="10Natural_resource_mgmt" & lever=="NRM: forest policies and regulations"
replace itype = "Producer subsidy" if segment=="10Natural_resource_mgmt" & lever=="NRM: renewable energy and energy efficiency"
replace itype = "	Public good	" if segment=="03Distribution_transport" & lever=="Rural roads and transport infrastructure"
replace itype = "	Public good	" if segment=="05Processing_manufacturing" & lever=="Processing and post production facilities"
replace itype = "	Regulations	" if segment=="03Distribution_transport" & lever=="Rules on food packaging"
replace itype = "	Regulations	" if segment=="03Distribution_transport" & lever=="Standards: safety/ quality/ traceability"
replace itype = "	Regulations	" if segment=="04Trade" & lever=="Competition policy"
replace itype = "	Regulations	" if segment=="05Processing_manufacturing" & lever=="rules on composition/ reformulation"
replace itype = "	Regulations	" if segment=="05Processing_manufacturing" & lever=="Rules on Promotion/Advertising"
replace itype = "	Regulations	" if segment=="05Processing_manufacturing" & lever=="Certification of Production Methods/Products"
replace itype = "	Regulations	" if segment=="05Processing_manufacturing" & lever=="Standards: Safety/Quality/Traceability"
replace itype = "	Regulations	" if segment=="06Retail" & lever=="Planning"
replace itype = "	Regulations	" if segment=="06Retail" & lever=="rules on promotion/ advertising"
replace itype = "	Regulations	" if segment=="06Retail" & lever=="Rules/ standards on provision"
replace itype = "	Regulations	" if segment=="06Retail" & lever=="Certification of Production Methods/Products"
replace itype = "	Regulations	" if segment=="06Retail" & lever=="Standards: Safety/Quality/Traceability"
replace itype = "	Regulations	" if segment=="07Foodservice" & lever=="procurement rules/ standards"
replace itype = "	Regulations	" if segment=="07Foodservice" & lever=="rules/ standards on provision"
replace itype = "	Regulations	" if segment=="07Foodservice" & lever=="Planning"
replace itype = "	Regulations	" if segment=="07Foodservice" & lever=="Certification of Production Methods/Products"
replace itype = "	Regulations	" if segment=="07Foodservice" & lever=="Composition/Reformulation (Food)"
replace itype = "	Regulations	" if segment=="07Foodservice" & lever=="Rules on Promotion/Advertising"
replace itype = "	Regulations	" if segment=="07Foodservice" & lever=="Standards: Safety/Quality/Traceability"
replace itype = "	Regulations	" if segment=="08Eating" & lever=="Rules on Promotion/Advertising"
replace itype = "	Regulations	" if segment=="09Multiple" & lever=="Food safety measures"
replace itype = "	Regulations	" if segment=="10Natural_resource_mgmt" & lever=="NRM: land ownership, tenure and titling"
replace itype = "	Regulations	" if segment=="10Natural_resource_mgmt" & lever=="NRM: land policy"
replace itype = "	Regulations	" if segment=="10Natural_resource_mgmt" & lever=="NRM: Water policies and regulations"
replace itype = "	Tax on consumer	" if segment=="06Retail" & lever=="Beverage container policy"
replace itype = "	Tax on consumer	" if segment=="08Eating" & lever=="DH - tax on unhealthy foods"
replace itype = "	Tax on consumer	" if segment=="08Eating" & lever=="DH - tax on SSB"
replace itype = "	Tax on consumer	" if segment=="08Eating" & lever=="Beverage container policy"
replace itype = "	Tax on consumer	" if segment=="08Eating" & lever=="VAT on food"
replace itype = "Tax on producer" if segment=="02Farming" & lever=="NRM: tax or fee on ag, fish, for or hunting"
replace itype = "Tax on producer" if segment=="02Farming" & lever=="PM: farm income or other unspecified ag tax"
replace itype = "Tax on producer" if segment=="05Processing_manufacturing" & lever=="Taxes"
replace itype = "Tax on producer" if segment=="07Foodservice" & lever=="Tax on processor"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Common market/Economic unions"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Customs Union"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Export - other export promotion measures"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Export - other export restrictions"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Export ban"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Export promotion - improved SPS standards"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Export quota"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Export subsidy"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Export tax"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Free or preferential trade agreement"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Government procurement through imports"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import - antidumping duties, countervailing duties, etc"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import - non tariff barrier - sanitary phytosanitary measures (SPS)"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import - non tariff barrier - technical barriers to trade"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import - other import restrictions"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import - tariff-rate quota"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import ban"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import quota"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import subsidy"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Import tariff"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Other trade-related measures"
replace itype = "	Trade policy	" if segment=="04Trade" & lever=="Trade facilitation"
sort itype		
tab itype	
tab defn

}	


//fixing EU wide policies and some other revisions 12 Sept

{
replace itype="NA" if framework==1
tab lever if itype=="."
tab defn if lever=="collaboration"
tab db if lever=="collaboration"
replace itype = "NA" if lever=="collaboration"
replace defn ="meetings of various stakeholders to make decisions related to making diets healthier" if lever =="collaboration"
tab lever if db=="Nourishing"



// Generate is_eu_country or eu_wide variable

replace country="Slovakia" if country=="Slovak Republic"

gen is_eu_country = 0
replace is_eu_country = 1 if inlist(country, "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark", "Estonia", "Finland")
replace is_eu_country = 1 if inlist(country, "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg")
replace is_eu_country = 1 if inlist(country, "Malta", "Netherlands", "Poland", "Portugal", "Romania")
replace is_eu_country = 1 if inlist(country, "Slovakia", "Slovenia", "Spain", "Sweden", "United Kingdom")

// generate is_eu_wide

gen is_eu_wide = 0
replace is_eu_wide = 1 if country == "European Union (EU)"

sort initialdate
//generate a non EU high income category


gen income_grp2=income_group
replace income_grp2="EUHighIncome" if income_group=="HighIncome" & is_eu_count==1 
replace income_grp2="nonEUHighIncome" if income_group=="HighIncome" & is_eu_count!=1
replace income_grp2="lowandmidinc" if income_group=="Low income" |income_group=="Lower middle income"|income_group=="Upper middle income"
//whether EU wide policy in given segment
tab income_group
tab lever if is_eu_country==1




//use "feb21withEU.dta", replace

replace is_eu_country = 1 if country == "European Union (EU)"
expand 28 if country == "European Union (EU)"

//Gives each copy a number from 1 to 28
bysort country id:  gen dup = cond(_N==1,0,_n)

replace country = "Korea, Rep." if country == "Korea"
replace country = "Serbia and Montenegro" if country == "Serbia" | country == "Montenegro"
bysort country (db): carryforward iso income_group region_wb fsd_group FAPDA_region FAPDA_subregion is_eu_country is_eu_wide, replace

replace level = "Supranational" if iso == ""


//Replaces the country name based on the number we gave. Kind of a bruteforce way, but it seems to work. Please note that the other variables (iso code, income group, region, fsd group) are still the same. So, ideally, we'll have to change those too.
replace country = "Austria" if dup == 28 & country == "European Union (EU)"
replace country = "Belgium" if dup == 1 & country == "European Union (EU)"
replace country = "Bulgaria" if dup == 2 & country == "European Union (EU)"
replace country = "Croatia" if dup == 3 & country == "European Union (EU)"
replace country = "Cyprus" if dup == 4 & country == "European Union (EU)"
replace country = "Czech Republic" if dup == 5 & country == "European Union (EU)"
replace country = "Denmark" if dup == 6 & country == "European Union (EU)"
replace country = "Estonia" if dup == 7 & country == "European Union (EU)"
replace country = "Finland" if dup == 8 & country == "European Union (EU)"
replace country = "France" if dup == 9 & country == "European Union (EU)"
replace country = "Germany" if dup == 10 & country == "European Union (EU)"
replace country = "Greece" if dup == 11 & country == "European Union (EU)"
replace country = "Hungary" if dup == 12 & country == "European Union (EU)"
replace country = "Ireland" if dup == 13 & country == "European Union (EU)"
replace country = "Italy" if dup == 14 & country == "European Union (EU)"
replace country = "Latvia" if dup == 15 & country == "European Union (EU)"
replace country = "Lithuania" if dup == 16 & country == "European Union (EU)"
replace country = "Luxembourg" if dup == 17 & country == "European Union (EU)"
replace country = "Malta" if dup == 18 & country == "European Union (EU)"
replace country = "Netherlands" if dup == 19 & country == "European Union (EU)"
replace country = "Poland" if dup == 20 & country == "European Union (EU)"
replace country = "Portugal" if dup == 21 & country == "European Union (EU)"
replace country = "Romania" if dup == 22 & country == "European Union (EU)"
replace country = "Slovakia" if dup == 23 & country == "European Union (EU)"
replace country = "Slovenia" if dup == 24 & country == "European Union (EU)"
replace country = "Spain" if dup == 25 & country == "European Union (EU)"
replace country = "Sweden" if dup == 26 & country == "European Union (EU)"
replace country = "United Kingdom" if dup == 27 & country == "European Union (EU)"
tab lever if dup!=0
tab dup
drop dup
drop if level=="Supranational" & is_eu_wide!=1
//drop if db=="FAPDA_F"
//no longer using expired since default is inclusion
tab segment if policy_code==2132

foreach var of varlist(topics){  
gen temp = lower(`var')
replace lever = "DH - dietary guidelines" if strpos(temp, "dietary guidelines") & strpos(temp, "adult*") == 0 & strpos(temp, "children") == 0 
replace lever = "DH - tax on SSB" if strpos(temp, "sugary drink") & strpos(temp, "tax") 
drop temp
}

list lever if country=="Mexico" & segment=="08Eating"
list lever if country=="United States" & segment=="08Eating"

replace segment = "09Multiple" if segment == "multiple"
replace segment = "11General_framework" if segment=="10frameworks"
drop policycategory
tab region_wb
tab fsd_group
tab country
tab db
tab level
tab covid_mentioned
*tab policy_description
tab iso
tab FAPDA_region
tab FAPDA_subregion


tab iso

drop checkme-positive_tse
drop yearofintroduction enddate
drop needtocheckmanually


drop if lever=="DH - dietary guidelines" & db=="FAPDA_F"
replace segment="11General_frameworks" if segment=="10frameworks"

replace segment = "08Final_consumption" if segment=="08Eating"



}


tab segment
save "March30.dta", replace

use "March30.dta", replace


//add info on levels of governance and frameworks

{
merge 1:1 _n using "states.dta"

replace state = lower(state)

levelsof state, local(state)

replace level = "National"
replace level = "NA" if country != "Brazil" & country != "Canada" & country != "China" & country != "Germany" & country != "India" & country != "Nigeria" & country != "United States"

gen temp = ""

foreach st of local state {
	replace temp = lower(policy_description)
	replace level = "Subnational" if strpos(temp, "`st'")
	replace temp = lower(policydecision_details)
	replace level = "Subnational" if strpos(temp,"`st'")
	replace temp = lower(contextoradditionalinfo)
	replace level = "Subnational" if strpos(temp,"`st'")
	replace temp = lower(beneficiaries)
	replace level = "Subnational" if strpos(temp,"`st'")
	replace temp = lower(generaltaxbase)
	replace level = "Subnational" if strpos(temp,"`st'")
	replace temp = lower(specifictaxbase)
	replace level = "Subnational" if strpos(temp,"`st'")
}

replace level = "NA" if country != "Brazil" & country != "Canada" & country != "China" & country != "Germany" & country != "India" & country != "Nigeria" & country != "United States"
drop temp

bysort country: gen order = _n
bysort country (order): carryforward iso income_group region_wb fsd_group FAPDA_region FAPDA_subregion is_eu_country is_eu_wide, replace
replace order = order * -1
bysort country (order): carryforward iso income_group region_wb fsd_group FAPDA_region FAPDA_subregion is_eu_country is_eu_wide, replace
replace order = order * -1
bysort country (order): carryforward iso income_group region_wb fsd_group FAPDA_region FAPDA_subregion is_eu_country is_eu_wide, replace
drop order


tab lever if db=="Nourishing"
tab lever if db=="PINE"
tab lever if db=="FAPDA"
tab lever if db=="FAPDA_F"


replace region="Europe & Central Asia" if country=="Belgium"
replace region="Europe & Central Asia" if country=="Cook Islands"
replace region="Europe & Central Asia" if country=="Cyprus"
replace region="Europe & Central Asia" if country=="Czech Republic"
replace region="Europe & Central Asia" if country=="Denmark"
replace region="Europe & Central Asia" if country=="Estonia"
replace region="Europe & Central Asia" if country=="Finland"
replace region="Europe & Central Asia" if country=="Latvia"
replace region="Europe & Central Asia" if country=="Netherlands"
replace region="Middle East & North Africa" if country=="Malta"
replace region="Europe & Central Asia" if country=="Latvia"
replace region="Europe & Central Asia" if country=="Serbia and Montenegro"
replace region="Europe & Central Asia" if country=="Sweden"
replace region="Europe & Central Asia" if country=="Ireland"
replace region="Europe & Central Asia" if country=="Greece"
replace region="East Asia & Pacific" if country=="Niue"


sort country
replace income_group="High income" if country=="Austria"
replace income_group="High income" if country=="Belgium"
replace income_group="High income" if country=="Croatia" 
replace income_group="High income" if country=="Cyprus" 
replace income_group="High income" if country=="Czech Republic"
replace income_group="High income" if country=="Estonia"
replace income_group="High income" if country=="Finland"
replace income_group="High income" if country=="Greece"
replace income_group="High income" if country=="Hungary"
replace income_group="High income" if country=="Ireland"
replace income_group="High income" if country=="Latvia"
replace income_group="High income" if country=="Lithuania"
replace income_group="High income" if country=="Luxembourg"
replace income_group="High income" if country=="Malta"
replace income_group="High income" if country=="Netherlands"
replace income_group="High income" if country=="Slovakia"
replace income_group="High income" if country=="Slovenia"
replace income_group="Upper middle income" if country=="Serbia and Montenegro"
replace income_group="Upper middle income" if country=="Bulgaria"
replace income_group="High income" if country=="Sweden"
replace income_group="High income" if country=="Slovenia"
replace income_group="High income" if country=="United Kingdom"
}
replace segment="08Final_consumption" if lever=="DH - tax on SSB"
replace segment="08Final_consumption" if lever=="Beverage container policy"
replace segment="08Final_consumption" if lever=="DH - dietary guidelines"

save "March30_f.dta", replace




