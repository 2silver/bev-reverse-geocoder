#!/usr/bin/env python3
import argparse
import psycopg2
import sys
import os.path
import csv


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Imports the Austrian BEV address data.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-H", "--hostname", dest="hostname", required=False, help="Host name or IP Address")
    parser.add_argument("-d", "--database", dest="database", default="gis", help="The name of the database")
    parser.add_argument("-t", "--table", dest="table", default="bev_addresses",
                        help="The database table to insert the data")
    parser.add_argument("-u", "--user", dest="user", required=False, help="The database user")
    parser.add_argument("-p", "--password", dest="password", required=False, help="The database password")
    parser.add_argument("-f", "--file", dest="file", required=True, help="The file to read from")
    args = parser.parse_args()

    # Try to connect
    try:
        conn = psycopg2.connect(
            host=args.hostname,
            database=args.database,
            user=args.user,
            password=args.password
        )
    except Exception as e:
        print("I am unable to connect to the database (%s)." % e.message)
        sys.exit(1)

    cursor = conn.cursor()

    if os.path.isfile(args.file):
        # Drop all data
        try:
            statement = "TRUNCATE TABLE " + args.table
            cursor.execute(statement)
        except Exception as e:
            print("Could not drop table data (%s)!" % e)
            sys.exit(1)

        # Iterate through the file and insert rows.
        with open(args.file) as f:
            # Skip the first line as it contains only the header.
            next(f)

            for line in csv.reader(f, quotechar='"', delimiter=";", quoting=csv.QUOTE_MINIMAL):
                statement = "INSERT INTO " + args.table + " VALUES (%s, %s, %s, %s, %s, null, ST_SetSRID(ST_MakePoint(%s, %s),4326))"

                # Do some basic data validation.
                if len(line) == 7 and is_float(line[5]) and is_float(line[6]):
                    try:
                        cursor.execute(statement, (
                            line[0], int(line[1]), line[2], line[3], line[4], line[6], line[5],)
                                       )
                    except Exception as e:
                        print("I can't insert the row '%s'! The exception was: %s" % (line, e,))
                        conn.rollback()
                        conn.close()
                        sys.exit(1)
                else:
                    print("There is something wrong with this line: '%s'. Please check if the column count is 7 and the data types are correct." % line)
    else:
        print("Unable to open the file '%s' as it does not exist." % args.file)

    # Make an "educated guess" about whether the address contains a proper street or a locality as the street name.
    try:
        cursor.execute("update bev_addresses set address_type='place'  where street     in (select name from bev_localities);")
        cursor.execute("update bev_addresses set address_type='street' where street not in (select name from bev_localities);")
    except Exception as e:
        print("Cannot set the address type! The exception was: %s" % (e,))
        conn.rollback()
        conn.close()
        sys.exit(1)

    # Commit all changes and close the connection.
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
