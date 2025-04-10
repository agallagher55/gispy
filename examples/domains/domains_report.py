import arcpy

import domains
import csv

from configparser import ConfigParser

from os import getcwd, environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

CURRENT_DIR = getcwd()

FEATURE = "SDEADM.LND_GFLUM"

if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    print(f"\nPC Name: {PC_NAME}\n\tRunning from: {run_from}...")

    for dbs in [
        [
            config.get("SERVER", "prod_rw"),
        ],

    ]:

        if dbs:
            print(f"\nProcessing dbs: {', '.join(dbs)}...")

            for db in dbs:
                print(f"\nDATABASE: {db}")

                with arcpy.EnvManager(workspace=db):

                    domain_info = list()

                    # Check for subtypes
                    subtypes = arcpy.da.ListSubtypes(FEATURE)

                    if len(subtypes) > 1:

                        for subtype in subtypes:

                            subtype_name = subtype

                            domain_fields = dict()

                            print(f"\nSubtype: '{subtype_name}' ({subtype})")

                            field_values = subtypes[subtype]['FieldValues']

                            for field in field_values:

                                print(f"\t{field}")
                                default, domain = field_values[field]

                                if domain:
                                    domain_name = domain.name

                                    print(f"\t\tDomain: {domain_name}")
                                    domain_fields[field] = domain_name
                                    coded_values = domain.codedValues

                                    domain_info.append(
                                        {
                                            "subtype": subtype_name,
                                            "field": field,
                                            "domain_name": domain_name,
                                            'coded_values': coded_values
                                        }
                                    )

                    print(domain_info)

                domain_info = sorted(domain_info, key=lambda x: x['subtype'])

                with open(f"{FEATURE}_domains.csv", "w", newline='') as csvfile:

                    fieldnames = [
                        "subtype",
                        "field",
                        "domain_name",
                        ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    writer.writerows([{k: v for k, v in x.items() if k in fieldnames} for x in domain_info])

                with open("domain_values.csv", "w", newline='') as csvfile:

                    fieldnames = ["domain", "code", "value"]
                    writer = csv.writer(csvfile)
                    writer.writerow(fieldnames)

                    unique_domains = sorted({domain['domain_name'] for domain in domain_info})

                    for domain in unique_domains:

                        # Find entry from domain_info
                        unique_domain_info = [x for x in domain_info if x['domain_name'] == domain][0]

                        coded_values = unique_domain_info.get('coded_values')

                        for code in coded_values:
                            writer.writerow([
                                domain,
                                code,
                                coded_values[code]
                            ])

