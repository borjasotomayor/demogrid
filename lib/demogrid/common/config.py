import ConfigParser
import csv

class DemoGridConfig(object):
    
    GENERAL_SEC = "general"
    ORGANIZATIONS_OPT = "organizations"
    MYPROXY_OPT = "myproxy"
    CACERT_OPT = "ca-cert"
    CAKEY_OPT = "ca-key"
    
    ORGANIZATION_SEC = "organization-"
    USERSFILE_OPT = "users-file"
    GRIDUSERS_OPT = "grid-users"
    GRIDUSERS_AUTH_OPT = "grid-users-auth"
    NONGRIDUSERS_OPT = "nongrid-users"
    GRAM_OPT = "gram"
    GRIDFTP_OPT = "gridftp"
    LRM_OPT = "lrm"
    CLUSTER_NODES_OPT = "cluster-nodes"

    EC2_SEC = "ec2"
    AMI_OPT = "ami"
    SNAP_OPT = "snap"
    KEYPAIR_OPT = "keypair"
    KEYFILE_OPT = "keyfile"
    INSTYPE_OPT = "instance_type"
    ZONE_OPT = "availability_zone"
    ACCESS_OPT = "access"

    
    def __init__(self, configfile):
        self.config = ConfigParser.ConfigParser()
        self.config.readfp(open(configfile, "r"))
        
        organizations = self.config.get(self.GENERAL_SEC, self.ORGANIZATIONS_OPT)
        self.organizations = organizations.split()

    def get_subnet(self):
        return "192.168" # This will be configurable

    def has_ca(self):
        return self.config.has_option(self.GENERAL_SEC, self.CACERT_OPT) and self.config.has_option(self.GENERAL_SEC, self.CAKEY_OPT)
    
    def get_ca(self):
        return self.config.get(self.GENERAL_SEC, self.CACERT_OPT), self.config.get(self.GENERAL_SEC, self.CAKEY_OPT)

    def has_grid_auth_node(self):
        return self.config.getboolean(self.GENERAL_SEC, self.MYPROXY_OPT)

    def has_org_users_file(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.has_option(org_sec, self.USERSFILE_OPT)    

    def get_org_users_file(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.get(org_sec, self.USERSFILE_OPT)    

    def get_org_num_gridusers(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.getint(org_sec, self.GRIDUSERS_OPT)    

    def get_org_num_nongridusers(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.getint(org_sec, self.NONGRIDUSERS_OPT)    

    def get_org_user_auth(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.get(org_sec, self.GRIDUSERS_AUTH_OPT)    
    
    def has_org_gridftp(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.getboolean(org_sec, self.GRIDFTP_OPT)

    def has_org_gram(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.getboolean(org_sec, self.GRAM_OPT)

    def has_org_auth(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.getboolean(org_sec, self.MYPROXY_OPT)
    
    def has_org_lrm(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        lrm = self.config.get(org_sec, self.LRM_OPT)
        return lrm != "none"
        
    def get_org_lrm(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.get(org_sec, self.LRM_OPT)
    
    def get_org_num_clusternodes(self, org_name):
        org_sec = self.__get_org_sec(org_name)
        return self.config.getint(org_sec, self.CLUSTER_NODES_OPT)
        
    def __get_org_sec(self, org_name):
        return self.ORGANIZATION_SEC + org_name
    
    def get_ami(self):
        return self.config.get(self.EC2_SEC, self.AMI_OPT)

    def has_snap(self):
        return self.config.has_option(self.EC2_SEC, self.SNAP_OPT)
    
    def get_snap(self):
        return self.config.get(self.EC2_SEC, self.SNAP_OPT)

    def get_keypair(self):
        return self.config.get(self.EC2_SEC, self.KEYPAIR_OPT)

    def get_keyfile(self):
        return self.config.get(self.EC2_SEC, self.KEYFILE_OPT)
    
    def get_instance_type(self):
        return self.config.get(self.EC2_SEC, self.INSTYPE_OPT)
    
    def get_ec2_zone(self):
        return self.config.get(self.EC2_SEC, self.ZONE_OPT)        
    
    def get_ec2_access_type(self):
        return self.config.get(self.EC2_SEC, self.ACCESS_OPT) 

            
        