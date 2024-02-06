from dataclasses import dataclass
from typing import List, Set, Tuple
from simulator import Agent, Grid
from .a_star_planner import AStarPlanner, manhattan_distance
from .task import Task
from .algorithm import Algorithm
from copy import deepcopy

class TPAgent:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.requires_token = True
        self.task = None
        self.final = self.agent.position

    def update(self):
        if len(self.agent.command_queue) <= 1:
            self.requires_token = True
        self.agent.update()

    @property
    def position(self):
        return self.agent.position

    def assign_path(self, path):
        self.agent.command_queue = [{"move_to": pos} for pos, _ in path]
        self.final, _ = path[0]


@dataclass
class Token:
    paths: dict
    tasks: List[Task]
    assign: dict


class TokenPassingTaskSwap(Algorithm):
    def __init__(self, agents: List[Agent], grid: Grid, tasks: List[Task]):
        self.grid = grid
        self.tp_agents = {ag: TPAgent(agent) for ag, agent in enumerate(agents)}
        self.timestep = 0
        self.token = Token(
            paths={
                ag: [(self.tp_agents[ag].agent.position, self.timestep)]
                for ag in self.tp_agents
            },
            tasks=tasks if tasks else [],
            assign={ag: None for ag in self.tp_agents}
        )
    @staticmethod
    def create_constraints_for_agent(agent: int, current_token: Token) -> Set[Tuple]:
        constraints = set()
        for ag in current_token.paths:
            if agent != ag:
                for pos, t in current_token.paths[ag]:
                    constraints.add((pos, t))  # vertex conflict constraint
                    constraints.add((pos, t + 1))  # edge conflict constraint
        return constraints

    def assign_path_to_agent(self, agent: int,current_token: Token, **kwargs):
        constraints = self.create_constraints_for_agent(agent, current_token)
        path_function = kwargs["path_function"] if "path_function" in kwargs else None
        if "path" in kwargs:
            path = kwargs["path"]
        elif path_function is not None:
            path = path_function(agent=self.tp_agents[agent], constraints=constraints, **kwargs)
        else:
            raise RuntimeError("Either specify a path or a path_function")
        current_token.paths[agent] = path
        self.tp_agents[agent].assign_path(path)

    def add_tasks(self, tasks: List[Task]):
        self.token.tasks += tasks 

    def path1(self, agent: TPAgent, task: Task, constraints: Set[Tuple], **kwargs):
        pos_to_pickup = AStarPlanner.plan(
            start_position=agent.position,
            target_position=task.s,
            grid=self.grid,
            constraints=constraints,
            timestep=self.timestep
        )
        pickup_to_end = AStarPlanner.plan(
            start_position=task.s,
            target_position=task.g,
            grid=self.grid,
            constraints=constraints,
            timestep=self.timestep + len(pos_to_pickup)
        )
        return pickup_to_end + pos_to_pickup

    def path2(self, agent: TPAgent, constraints: Set[Tuple], **kwargs):
        return AStarPlanner.plan(
            start_position=agent.position,
            target_position=agent.agent.starting_position,
            grid=self.grid,
            constraints=constraints,
            timestep=self.timestep
        )

    def get_task(self, agent_key: int, current_token: Token) -> bool:
        #print("AGENT KEY", agent_key)
        #print(f"{current_token=}")
        cur_agent = self.tp_agents[agent_key]

        #other_agents_endpoints = [
        #    current_token.paths[ag][0][0]
        #    for ag in current_token.paths
        #    if ag != agent_key
        #]
        clear_tasks = []
        for t in current_token.tasks:
            for executing_agents_key in current_token.paths:
                endpoint = current_token.paths[executing_agents_key][0]
                if t != current_token.assign[executing_agents_key] and t.s != endpoint and t.g != endpoint:
                    clear_tasks.append(t)
                    
        #clear_tasks = list(filter(
        #    lambda t : t.s not in other_agents_endpoints and t.g not in other_agents_endpoints,
        #    current_token.tasks
        #))
        #clear_tasks = [
        #    t for t in current_token.tasks
        #    if t.s not in other_agents_endpoints and t.g not in other_agents_endpoints
        #]

        tasks_with_goal_eq_agent_pos = set(filter(
            lambda t: t.g == cur_agent.agent.position,
            current_token.tasks
        ))

        #tasks_with_goal_eq_agent_pos = {
        #    t for t in current_token.tasks
        #    if t.g == cur_agent.position
        #}

        while clear_tasks:
            #print(f"{clear_tasks=}")
            task = min(
                clear_tasks,
                key=lambda t: manhattan_distance(cur_agent.position, t.s)
            )
            #print(f"{task=}")
            clear_tasks.remove(task)
            assigned_tasks = list(current_token.assign.values())
            #print(current_token.assign)
            if task not in assigned_tasks:
                current_token.assign[agent_key] = task
                self.assign_path_to_agent(
                    agent=agent_key,
                    current_token=current_token,
                    path_function=self.path1,
                    task=task
                )
                #print("TASK", task, "ASSIGNED TO", agent_key)
                return True
            else:
                #print("OPPORTUNITY")
                token_copy = deepcopy(current_token)
                agents = list(current_token.assign.keys())
                agent_assigned_to_task = agents[assigned_tasks.index(task)]
                current_token.assign[agent_assigned_to_task] = None
                current_token.assign[agent_key] = task
                new_path = self.path1(cur_agent, task, self.create_constraints_for_agent(agent_key, current_token))
                _, new_timestep = new_path[0]
                _, old_timestep = current_token.paths[agent_assigned_to_task][0]
                #print(new_timestep, old_timestep)
                if new_timestep < old_timestep:
                    #print("takes less time")
                    if self.get_task(agent_assigned_to_task, current_token):
                        print(f"TASK SWAPPED {agent_key}->{agent_assigned_to_task}")
                        self.assign_path_to_agent(agent=agent_key, current_token=current_token, path=new_path)
                        return True
                #print("Restoring token")
                self.token = token_copy
                current_token = self.token
            if cur_agent.position != cur_agent.agent.starting_position:
                #print("GO HOME")
                self.assign_path_to_agent(agent=agent_key, current_token=current_token, path_function=self.path2)
            else:
                if not tasks_with_goal_eq_agent_pos:
                    #print("stay")
                    self.assign_path_to_agent(agent=agent_key, current_token=current_token, path=[(cur_agent.position, self.timestep)])
                    #print(current_token)
                else:
                    #print("GO HOME")
                    self.assign_path_to_agent(agent=agent_key, current_token=current_token, path_function=self.path2)
                return True
        return False

    def update(self):
        while any([self.tp_agents[ag].requires_token for ag in self.tp_agents]):
            for agent_key in self.tp_agents:
                if self.tp_agents[agent_key].requires_token:
                    # Token is assigned to agent
                    self.tp_agents[agent_key].requires_token = False
                    self.get_task(agent_key, self.token)
        for agent_key in self.tp_agents:
            self.tp_agents[agent_key].update()
            task_assigned_to_agent = self.token.assign[agent_key]
            if task_assigned_to_agent:
                if self.tp_agents[agent_key].position == task_assigned_to_agent.s and task_assigned_to_agent in self.token.tasks:
                    self.token.tasks.remove(self.token.assign[agent_key])
        self.timestep += 1

