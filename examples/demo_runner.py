# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.


import math
import multiprocessing
import os
import random
import torch
import sys
import time
from enum import Enum

import numpy as np
from PIL import Image
from settings import default_sim_settings, make_cfg

import habitat_sim
import habitat_sim.agent
import habitat_sim.bindings as hsim
from habitat_sim.utils.common import (
    d3_40_colors_rgb,
    download_and_unzip,
    quat_from_angle_axis,
)

_barrier = None


class DemoRunnerType(Enum):
    BENCHMARK = 1
    EXAMPLE = 2


class DemoRunner:
    def __init__(self, sim_settings, simulator_demo_type):
        if simulator_demo_type == DemoRunnerType.EXAMPLE:
            self.set_sim_settings(sim_settings)

    def init_yolo(self, data_config, classes, weights_path):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        data_config = parse_data_config(data_config)
        valid_path = data_config["valid"]
        class_names = load_classes(classes)

        # Initiate model
        model = Darknet(opt.model_def).to(device)
        if opt.weights_path.endswith(".weights"):
            # Load darknet weights
            model.load_darknet_weights(opt.weights_path)
        else:
            # Load checkpoint weights
            model.load_state_dict(torch.load(opt.weights_path))


    def set_sim_settings(self, sim_settings):
        self._sim_settings = sim_settings.copy()

    def save_color_observation(self, obs, total_frames):
        color_obs = obs["color_sensor"]
        color_img = Image.fromarray(color_obs, mode="RGBA")
        color_img.save("test.rgba.%05d.png" % total_frames)

    def save_semantic_observation(self, obs, total_frames):
        semantic_obs = obs["semantic_sensor"]
        semantic_img = Image.new("P", (semantic_obs.shape[1], semantic_obs.shape[0]))
        semantic_img.putpalette(d3_40_colors_rgb.flatten())
        semantic_img.putdata((semantic_obs.flatten() % 40).astype(np.uint8))
        semantic_img.save("test.sem.%05d.png" % total_frames)

    def save_depth_observation(self, obs, total_frames):
        if self._sim_settings["depth_sensor"]:
            depth_obs = obs["depth_sensor"]
            depth_img = Image.fromarray(
                (depth_obs / 10 * 255).astype(np.uint8), mode="L"
            )
            depth_img.save("test.depth.%05d.png" % total_frames)

    def output_semantic_mask_stats(self, obs, total_frames):
        semantic_obs = obs["semantic_sensor"]
        counts = np.bincount(semantic_obs.flatten())
        total_count = np.sum(counts)
        print(f"Pixel statistics for frame {total_frames}")
        for object_i, count in enumerate(counts):
            sem_obj = self._sim.semantic_scene.objects[object_i]
            cat = sem_obj.category.name()
            pixel_ratio = count / total_count
            if pixel_ratio > 0.01:
                print(f"obj_id:{sem_obj.id},category:{cat},pixel_ratio:{pixel_ratio}")

    def init_agent_state(self, agent_id):
        # initialize the agent at a random start state
        agent = self._sim.initialize_agent(agent_id)
        start_state = agent.get_state()

        # force starting position on first floor (try 100 samples)
        num_start_tries = 0
        while start_state.position[1] > 0.5 and num_start_tries < 100:
            start_state.position = self._sim.pathfinder.get_random_navigable_point()
            num_start_tries += 1
        agent.set_state(start_state)

        if not self._sim_settings["silent"]:
            print(
                "start_state.position\t",
                start_state.position,
                "start_state.rotation\t",
                start_state.rotation,
            )

        return start_state

    def compute_shortest_path(self, start_pos, end_pos):
        self._shortest_path.requested_start = start_pos
        self._shortest_path.requested_end = end_pos
        self._sim.pathfinder.find_path(self._shortest_path)
        print("shortest_path.geodesic_distance", self._shortest_path.geodesic_distance)

    def init_physics_test_scene(self, num_objects):
        object_position = np.array(
            [-0.569043, 2.04804, 13.6156]
        )  # above the castle table

        # turn agent toward the object
        print("turning agent toward the physics!")
        agent_state = self._sim.get_agent(0).get_state()
        agent_to_obj = object_position - agent_state.position
        agent_local_forward = np.array([0, 0, -1.0])
        flat_to_obj = np.array([agent_to_obj[0], 0.0, agent_to_obj[2]])
        flat_dist_to_obj = np.linalg.norm(flat_to_obj)
        flat_to_obj /= flat_dist_to_obj
        # move the agent closer to the objects if too far (this will be projected back to floor in set)
        if flat_dist_to_obj > 3.0:
            agent_state.position = object_position - flat_to_obj * 3.0
        # unit y normal plane for rotation
        det = (
            flat_to_obj[0] * agent_local_forward[2]
            - agent_local_forward[0] * flat_to_obj[2]
        )
        turn_angle = math.atan2(det, np.dot(agent_local_forward, flat_to_obj))
        agent_state.rotation = quat_from_angle_axis(turn_angle, np.array([0, 1.0, 0]))
        # need to move the sensors too
        for sensor in agent_state.sensor_states:
            agent_state.sensor_states[sensor].rotation = agent_state.rotation
            agent_state.sensor_states[
                sensor
            ].position = agent_state.position + np.array([0, 1.5, 0])
        self._sim.get_agent(0).set_state(agent_state)

        # hard coded dimensions of maximum bounding box for all 3 default objects:
        max_union_bb_dim = np.array([0.125, 0.19, 0.26])

        # add some objects in a grid
        object_lib_size = self._sim.get_physics_object_library_size()
        object_init_grid_dim = (3, 1, 3)
        object_init_grid = {}
        assert (
            object_lib_size > 0
        ), "!!!No objects loaded in library, aborting object instancing example!!!"
        for obj_id in range(num_objects):
            rand_obj_index = random.randint(0, object_lib_size - 1)
            # rand_obj_index = 0  # overwrite for specific object only
            object_init_cell = (
                random.randint(-object_init_grid_dim[0], object_init_grid_dim[0]),
                random.randint(-object_init_grid_dim[1], object_init_grid_dim[1]),
                random.randint(-object_init_grid_dim[2], object_init_grid_dim[2]),
            )
            while object_init_cell in object_init_grid:
                object_init_cell = (
                    random.randint(-object_init_grid_dim[0], object_init_grid_dim[0]),
                    random.randint(-object_init_grid_dim[1], object_init_grid_dim[1]),
                    random.randint(-object_init_grid_dim[2], object_init_grid_dim[2]),
                )
            object_id = self._sim.add_object(rand_obj_index)
            object_init_grid[object_init_cell] = object_id
            object_offset = np.array(
                [
                    max_union_bb_dim[0] * object_init_cell[0],
                    max_union_bb_dim[1] * object_init_cell[1],
                    max_union_bb_dim[2] * object_init_cell[2],
                ]
            )
            self._sim.set_translation(object_position + object_offset, object_id)
            print(
                "added object: "
                + str(object_id)
                + " of type "
                + str(rand_obj_index)
                + " at: "
                + str(object_position + object_offset)
                + " | "
                + str(object_init_cell)
            )





    def do_time_steps(self):
        total_frames = 0
        start_time = time.time()
        print(self._sim_settings)
        action_names = list(
            self._cfg.agents[self._sim_settings["default_agent"]].action_space.keys()
        )

        # load an object and position the agent for physics testing
        if self._sim_settings["enable_physics"]:
            self.init_physics_test_scene(num_objects=10)
            print("active object ids: " + str(self._sim.get_existing_object_ids()))

        time_per_step = []
        action = random.choice(action_names)
        observations = self._sim.step(action)

        print(observations)

        while total_frames < self._sim_settings["max_frames"]:
            if total_frames == 1:
                start_time = time.time()
            if not self._sim_settings["silent"]:
                print("action", action)

            start_step_time = time.time()
            # NOTE: uncomment this for random kinematic transform setting of all objects
            # if self._sim_settings["enable_physics"]:
            #    obj_ids = self._sim.get_existing_object_ids()
            #    for obj_id in obj_ids:
            #        rand_nudge = np.random.uniform(-0.05,0.05,3)
            #        cur_pos = self._sim.get_translation(obj_id)
            #        self._sim.set_translation(cur_pos + rand_nudge, obj_id)
            time_per_step.append(time.time() - start_step_time)
            if self._sim_settings['display_frame']:
                import cv2
                cv2.imshow("Frame", observations["color_sensor"])
                key = cv2.waitKey(0)
                print(key)
                if key == 82:
                    action = 'move_forward'
                elif key == 81:
                    action = 'turn_left'
                elif key == 83:
                    action = 'turn_right'
                print(action_names)
            observations = self._sim.step(action)

            if self._sim_settings["save_png"]:
                if self._sim_settings["color_sensor"]:
                    self.save_color_observation(observations, total_frames)
                if self._sim_settings["depth_sensor"]:
                    self.save_depth_observation(observations, total_frames)
                if self._sim_settings["semantic_sensor"]:
                    self.save_semantic_observation(observations, total_frames)

            state = self._sim.last_state()

            if not self._sim_settings["silent"]:
                print("position\t", state.position, "\t", "rotation\t", state.rotation)

            replica_pos, replica_rot = self.convert_habitat_to_replica(state.position, state.rotation)
            print("Replica Pos:" + str(replica_pos) + " " + " Replica Rot:" + str(replica_rot))

            if self._sim_settings["compute_shortest_path"]:
                print("Goal: " + str(self._sim_settings['goal_position']))

                self.compute_shortest_path(
                    state.position, self._sim_settings["goal_position"]
                )

            if self._sim_settings["compute_action_shortest_path"]:
                self._action_shortest_path.requested_start.position = state.position
                self._action_shortest_path.requested_start.rotation = state.rotation
                self._action_pathfinder.find_path(self._action_shortest_path)
                print(
                    "len(action_shortest_path.actions)",
                    len(self._action_shortest_path.actions),
                )

            if (
                self._sim_settings["semantic_sensor"]
                and self._sim_settings["print_semantic_mask_stats"]
            ):
                self.output_semantic_mask_stats(observations, total_frames)

            total_frames += 1

        end_time = time.time()
        perf = {}
        perf["total_time"] = end_time - start_time
        perf["frame_time"] = perf["total_time"] / total_frames
        perf["fps"] = 1.0 / perf["frame_time"]
        perf["time_per_step"] = time_per_step

        return perf

    def print_semantic_scene(self):
        if self._sim_settings["print_semantic_scene"]:
            scene = self._sim.semantic_scene
            print(f"House center:{scene.aabb.center} dims:{scene.aabb.sizes}")
            for level in scene.levels:
                print(
                    f"Level id:{level.id}, center:{level.aabb.center},"
                    f" dims:{level.aabb.sizes}"
                )
                for region in level.regions:
                    print(
                        f"Region id:{region.id}, category:{region.category.name()},"
                        f" center:{region.aabb.center}, dims:{region.aabb.sizes}"
                    )
                    for obj in region.objects:
                        print(
                            f"Object id:{obj.id}, category:{obj.category.name()},"
                            f" center:{obj.aabb.center}, dims:{obj.aabb.sizes}"
                        )
            input("Press Enter to continue...")

    def init_common(self):
        self._cfg = make_cfg(self._sim_settings)
        scene_file = self._sim_settings["scene"]

        if (
            not os.path.exists(scene_file)
            and scene_file == default_sim_settings["test_scene"]
        ):
            print(
                "Test scenes not downloaded locally, downloading and extracting now..."
            )
            download_and_unzip(default_sim_settings["test_scene_data_url"], ".")
            print("Downloaded and extracted test scenes data.")

        self._sim = habitat_sim.Simulator(self._cfg)
        print(self._sim.config)

        random.seed(self._sim_settings["seed"])
        self._sim.seed(self._sim_settings["seed"])

        # initialize the agent at a random start state
        start_state = self.init_agent_state(self._sim_settings["default_agent"])

        return start_state

    def _bench_target(self, _idx=0):
        self.init_common()

        best_perf = None
        for _ in range(3):

            if _barrier is not None:
                _barrier.wait()
                if _idx == 0:
                    _barrier.reset()

            perf = self.do_time_steps()
            # The variance introduced between runs is due to the worker threads
            # being interrupted a different number of times by the kernel, not
            # due to difference in the speed of the code itself.  The most
            # accurate representation of the performance would be a run where
            # the kernel never interrupted the workers, but this isn't
            # feasible, so we just take the run with the least number of
            # interrupts (the fastest) instead.
            if best_perf is None or perf["frame_time"] < best_perf["frame_time"]:
                best_perf = perf

        self._sim.close()
        del self._sim

        return best_perf

    @staticmethod
    def _pool_init(b):
        global _barrier
        _barrier = b

    def benchmark(self, settings):
        self.set_sim_settings(settings)
        nprocs = settings["num_processes"]

        barrier = multiprocessing.Barrier(nprocs)
        with multiprocessing.Pool(
            nprocs, initializer=self._pool_init, initargs=(barrier,)
        ) as pool:
            perfs = pool.map(self._bench_target, range(nprocs))

        res = {k: [] for k in perfs[0].keys()}
        for p in perfs:
            for k, v in p.items():
                res[k] += [v]

        return dict(
            frame_time=sum(res["frame_time"]),
            fps=sum(res["fps"]),
            total_time=sum(res["total_time"]) / nprocs,
        )

    def convert_habitat_to_replica(self, pos, rot):
        import quaternion
        # Define the transforms needed
        _tmp = np.eye(3, dtype=np.float32)
        UnitX = _tmp[0]
        UnitY = _tmp[1]
        UnitZ = _tmp[2]

        R_hsim_replica = habitat_sim.utils.quat_from_two_vectors(-UnitZ, -UnitY)
        T_hsim_replica = np.eye(4, dtype=np.float32)
        T_hsim_replica[0:3, 0:3] = quaternion.as_rotation_matrix(R_hsim_replica)

        R_forward_back = habitat_sim.utils.quat_from_two_vectors(-UnitZ, UnitZ)
        T_replicac_hsimc = np.eye(4, dtype=np.float32)
        T_replicac_hsimc[0:3, 0:3] = quaternion.as_rotation_matrix(R_forward_back)

        # Transforming the state happens here
        T_hsim_c = np.eye(4, dtype=np.float32)
        T_hsim_c[0:3, 0:3] = quaternion.as_rotation_matrix(rot)
        T_hsim_c[0:3, 3] = pos

        T_c_hsim = np.linalg.inv(T_hsim_c)
        T_c_replica = T_replicac_hsimc @ T_c_hsim @ T_hsim_replica

        T_replica_c = np.linalg.inv(T_c_replica)

        replica_pos = T_replica_c[0:3, 3]
        replica_rot = quaternion.from_rotation_matrix(T_replica_c[0:3, 0:3])

        return replica_pos, replica_rot


    def example(self):
        start_state = self.init_common()

        # initialize and compute shortest path to goal
        if self._sim_settings["compute_shortest_path"]:
            self._shortest_path = hsim.ShortestPath()

            self.compute_shortest_path(
                start_state.position, self._sim_settings["goal_position"]
            )


        # set the goal headings, and compute action shortest path
        if self._sim_settings["compute_action_shortest_path"]:
            agent_id = self._sim_settings["default_agent"]
            goal_headings = self._sim_settings["goal_headings"]

            self._action_pathfinder = self._sim.make_action_pathfinder(agent_id)

            self._action_shortest_path = hsim.MultiGoalActionSpaceShortestPath()
            self._action_shortest_path.requested_start.position = start_state.position
            self._action_shortest_path.requested_start.rotation = start_state.rotation

            # explicitly reset the start position
            self._shortest_path.requested_start = start_state.position

            # initialize the requested ends when computing the action shortest path
            next_goal_idx = 0
            while next_goal_idx < len(goal_headings):
                sampled_pos = self._sim.pathfinder.get_random_navigable_point()
                self._shortest_path.requested_end = sampled_pos
                if (
                    self._sim.pathfinder.find_path(self._shortest_path)
                    and self._shortest_path.geodesic_distance < 5.0
                    and self._shortest_path.geodesic_distance > 2.5
                ):
                    self._action_shortest_path.requested_ends.append(
                        hsim.ActionSpacePathLocation(
                            sampled_pos, goal_headings[next_goal_idx]
                        )
                    )
                    next_goal_idx += 1

            self._shortest_path.requested_end = self._sim_settings["goal_position"]
            print("Goal: " + str(self._sim_settings['goal_position']))
            self._sim.pathfinder.find_path(self._shortest_path)

            self._action_pathfinder.find_path(self._action_shortest_path)
            print(
                "len(action_shortest_path.actions)",
                len(self._action_shortest_path.actions),
            )

        # print semantic scene
        self.print_semantic_scene()

        perf = self.do_time_steps()
        self._sim.close()
        del self._sim

        return perf
