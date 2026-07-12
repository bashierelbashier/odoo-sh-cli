*Odoo.sh platform CLI tool*


This tool is supposed to be an RPA tool to manage Odoo.sh projects.

Mechanism:
* There should be a github user which we can create, then link with the tool here
* The tool must be able to authenticate to the user in github.com and use it to login to odoo.sh
* The tool will use robotframework's RPA capabilities to manage the project in odoo.sh from CLI
* Example available commands:
   - Rebuild a branch
   - Update the default feature branch configuration
   - Create a backup
   - Download a backup
   - Restore a backup
   - Delete a branch
   - Set domains for an instance
   - Check logs and monitor
   - Run upgrades and get status
   - Update settings of branches
   - Update project settings like commit status token, etc
