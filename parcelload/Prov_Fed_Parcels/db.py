# Function: sql_script
# Author: Neil Kenny
# Date: Jan 17, 2011

import os
import subprocess

def sql_script(dbUser, dbPassword, dbInst, scriptPath, parameter1=""):
  """
  Builds and executes commands for executing SQL*Plus with defined SQL script files.
  #   dbUser - Database user (String)
  #   dbPassword - Database user's password (String)
  #   dbInst - The instance of the database (String)
  #   scriptPath - Path to the SQL script to execute (String)
  #   parameter1 - Paraemter to pass to SQL*Plus (String)
  """
  
    try:
        if os.path.isfile(scriptPath):
            credentials = dbUser + "/" + dbPassword + "@" + dbInst
            
          if parameter1 != "":
                proc = subprocess.Popen(["sqlplus", credentials, "@" + scriptPath, parameter1], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
              
            else:
                proc = subprocess.Popen(["sqlplus", credentials, "@" + scriptPath], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

            return proc.communicate()
      
        else:
            raise Exception("SQL Script file does not exist")
          
    except:
        print("Error executing SQL*Plus script.")
        raise


if __name__ == "__main__":
  queryResult, errorMessage = sql_script(
                config.get(instance, 'username'), 
                config.get(instance, 'password'), 
                config.get(instance, 'dbinstance'), 
                scriptsDir + filename
            )
