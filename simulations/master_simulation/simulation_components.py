import random
import simpy
import datetime
import numpy as np
import copy
import pandas as pd

class Node:
    #Node states based on Antonio's diagramming on Feb 15 2019
    #Assume staking mechanism is complete
    def __init__(self, env, identity, start_time, tickets):
        self.env = env
        self.id = identity
        self.starttime = start_time
        self.process = env.process(self.Connect_Node(env))
        self.relay_request_time = 0
        self.relay_entry_watch_time = 0
        self.ingroup = False
        self.inrelay = False
        self.number_of_entries_generated = 0
        self.groups_joined= [] #keeps track of groups joined by this node
        self.STAKING_AMT = np.random.lognormal(3,1,) #find total tokens from contract
        self.cycle_count = 0
        self.node_status = "online" #change later to event - currently used for node failure process
        self.reconnect_event = env.event() #used to trigger node reconnection


    #Connecting to Ethereum
    def Connect_Node(self, env):
        while True:
            #self.node_failure_generator() 
            #if self.node_status == "failed": yield self.env.timeout(1) #checks if the node has failed
            ethereum_conection_time = np.random.randint(1,100) #assumes a linear distribution 
            if ethereum_conection_time>=90:
                #print (str(self.id) + " ethereum connection Failure" + "cycle=" + str(self.cycle_count))
                self.current_state = "not connected"
                self.reconnect_event = env.event()
            else:
                #print (str(self.id) + " ethereum connection success" + "cycle="+str(self.cycle_count))            
                self.current_state = "connected"
                yield self.env.process(self.Forking_MainLoop(env))
    
    def Forking_MainLoop(self,env):
        while True:
            self.node_failure_generator()
            if self.node_status == "failed": yield env.exit()
            print(str(self.id) + " Forking Main Loop" + " cycle="+str(self.cycle_count))
            yield self.env.process(self.Watching_RelayRequest(env))
        #env.process(self.Watching_RelayRequest(env))
        #env.process(self.Watching_RelayEntry(env))  
    
     # wait for relay request
    def Watching_RelayRequest(self, env):
        #self.node_failure_generator()
        #if self.node_status == "failed": yield env.exit()
        yield self.reconnect_event #stops watching if reconnect event is triggered 

    #join group
    def join_group(self, env, group_object):
        #self.node_failure_generator()
        #if self.node_status == "failed": yield env.exit()
        if group_object.group[self.id]:
            print(self.id)
            print("Node# = "+ str(self.id) + "joining group")
            group_object.connect(self.id)
            yield env.timeout(1)
        else:
            print("Node# = "+ str(self.id) +" did not join group")
            yield env.timeout(1)

    def node_failure_generator(self):
        failure = np.random.lognormal(1,0)
        if failure < 0.5 or failure >1.5 :
            self.node_status = "failed"
        yield self.node_status

def min_index(ticket_array, group_size):
    array = copy.deepcopy(ticket_array)
    group = sorted(array)[0:group_size] # generates a sorted list of min values of length = group size
    #print(group)
    indexes = [] #initializes the array of indexes for min ticket values
    
    for ticket in group: #iterates through each ticket value in the sorted list
        
        ticket_index = np.where(array==(ticket)) #finds the index with the ticket value
        #print("ticket_index = " + str(ticket_index))
        indexes.append(ticket_index[0][0]) # adds the index value to the array of indexes
        #print("indexes = " + str(indexes))
        array[ticket_index[0][0]] = 1 #sets the vaue at that index to the max value of 1 to address the problem of repeatd values
        
    #print(ticket_array_temp)
    return sorted(indexes)

def preprocess_tickets(runs, total_tickets):
# Pre-processing ticket arrays
# runs = number of simulation runs
# total_tickets = total # of tickets (virtual stakers)
    tickets=[]
    for i in range(0, runs):
        tickets.append(np.random.random_sample(int(total_tickets)))
    return tickets

def preprocess_groups(tickets, runs, group_size):
# Pre-processing groups
    group_members = []
    for i in range(0, runs):
        group_members.append(min_index(tickets[i],group_size)) # finds the index of group members with min ticket values
    return group_members

def create_cdf(nodes,ticket_distr):
# Create CDF's - used to determine max ownership ticket index
    cdf = np.zeros(nodes)
    for node,ticketmax in enumerate(ticket_distr):
        
        cdf[node]=sum(ticket_distr[0:node+1])
    return cdf

def group_distr(runs, nodes, group_members, cdf):
# function to calculate group ownership distribution
    total_group_distr = np.zeros(nodes)
    max_owned = np.zeros(runs)
    group_distr_matrix = np.zeros((runs,nodes))
    for i in range(runs):
        group_distr = np.zeros(nodes)
        group_distr[1] = sum(group_members[i]<cdf[0])
        for j in range(1,nodes):
            group_distr[j] = sum(group_members[i]<cdf[j])-sum(group_members[i]<cdf[j-1])
        max_owned[i] = max(group_distr)/sum(group_distr)
        total_group_distr +=group_distr
        group_distr_matrix[i] = group_distr #saves the group ticket distribution for each run
        print(group_distr_matrix[i])
    return total_group_distr, max_owned, group_distr_matrix

def node_failure_modes(nodes, runs):
# Calculates if a node has gone offline
# https://livemap.pingdom.com/
    timeout = np.random.rand(nodes, runs) < 0.15
    return timeout

class Group:
    #Group class
    def __init__(self, env, identity, group_size, group_distr_matrix):
        self.cycle = 0
        self.tries = 0
        self.failures = 0
        self.current_member_count = 0
        self.status = "inactive"
        self.id = identity
        self.member_check = np.zeros(group_size) #tally of how many members are currently connected to the group
        self.group = np.array(group_distr_matrix[self.id]) > 0 # the group distribution
        self.signing_events =[]

    def connect(self, node_id):
        self.member_check[node_id] = 1
    
    def disconnect(self, node_id):
        self.member_check[node_id] = 0

    def is_ready(self):

        if self.status == "inactive" and np.array_equal(self.member_check, self.group):
            self.status == "active"
        elif self.status == "active" and np.array_equal(self.member_check, self.group):
            self.status == "active"
        elif self.status == "inactive":
            self.status == "pending"
        elif self.status == "active" and not np.array_equal(self.member_check, self.group):
            self.status == "failed"
        else:
            self.status == "uknown error"
    

def relay_entry(env, runs, group_object_array, node_object_array):
    sign_successes =[]
    entry_cycles = 0
    while True:
        entry_cycles += 1
        print("run # = "+str(entry_cycles))
        group = group_object_array[np.random.randint(0,runs-1)] #picks the group id to perform the signature
        for node in node_object_array:
            yield env.process(node.join_group(env, group))
        
        group.is_ready() #check if the group is ready
        print(group.member_check)

        if group.status == "active":
            print("group ready, begin signing")
            sign_successes.append(1) # if ready add 1 to successfull signing events array
            # add signing process here
        else:
            print("group not ready, signing failed")
            sign_successes.append(0) # if not ready add 0 to successful signing events array

        if entry_cycles == runs : yield env.exit()
        
    









    
        

        
        


        



    









""" # Setup and start the simulation
sim_cycles = 5
TOTAL_TOKEN_AMT = 100

print('Node States')

# Create an environment and start the setup process
env = simpy.Environment()
print("creating nodes")
nodes = [Node(env, 'Node %d' % i, datetime.datetime.now(), sim_cycles)
            for i in range(100)] #number of nodes
env.run()
print("xxxxxxxxxxxxxxxxxxxx")
print(" final node states ")
for n in nodes:
    print(str(n.id) + ", # of Entries = " 
    + str(n.number_of_entries_generated) 
    + ", # Groups Joined = " 
    + str(n.number_of_groups_joined)
    + ", Total relay request time = "
    + str(n.relay_request_time)
    + ", Total relay watch time = "
    + str(n.relay_entry_watch_time)
    + ", Node Status = " + str(n.node_status))  """