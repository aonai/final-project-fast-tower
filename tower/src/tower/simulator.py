""" 
Uses the MoveIt Python API to create a planning scene and perform some path planning tasks

"""
import sys
import copy
import rospy
import moveit_commander
import moveit_msgs.msg
import geometry_msgs.msg
from math import pi
from std_msgs.msg import String
from moveit_commander.conversions import pose_to_list
from moveit_msgs.msg import MoveItErrorCodes
from gazebo_msgs.srv import GetModelState,SetModelState
from geometry_msgs.msg import Pose,Point,Twist
from gazebo_msgs.msg import ModelState
import tf2_ros





def all_close(goal, actual, tolerance):
  """
  Convenience method for testing if a list of values are within a tolerance of their counterparts in another list
  @param: goal       A list of floats, a Pose or a PoseStamped
  @param: actual     A list of floats, a Pose or a PoseStamped
  @param: tolerance  A float
  @returns: bool
  """
  all_equal = True
  if type(goal) is list:
    for index in range(len(goal)):
      if abs(actual[index] - goal[index]) > tolerance:
        return False

  elif type(goal) is geometry_msgs.msg.PoseStamped:
    return all_close(goal.pose, actual.pose, tolerance)

  elif type(goal) is geometry_msgs.msg.Pose:
    return all_close(pose_to_list(goal), pose_to_list(actual), tolerance)

  return True

class Scene():
    def __init__(self,myscene,REAL_ROBOT):
        """ Initiates a `PlanningSceneInterface`_ object.  This object is an interface
        to the world surrounding the robot. Object geometry variables are assigned from yaml file
        and the object postions are assigned from gazebo or computer vision (april tag locations)
        """
        rospy.loginfo("INIT Scene")
        self.scene = myscene
        if(REAL_ROBOT):
            self.gms = self.fake_gms
            self.sms = self.fake_sms
        else:
            self.gms = rospy.ServiceProxy("/gazebo/get_model_state",GetModelState)
            self.sms = rospy.ServiceProxy("/gazebo/set_model_state",SetModelState)


        rospy.loginfo("added scene")

        # OBJECT VARIABLES
        self.cup_radius = rospy.get_param("radius") # cup size
        self.cup_height = rospy.get_param("length")
        self.table_x = rospy.get_param("table_x")
        self.table_y = rospy.get_param("table_y")
        self.table_z = rospy.get_param("table_z")
        self.table_posx = rospy.get_param("t_x")    
        self.table_posy = rospy.get_param("t_y")
        self.table_posz = rospy.get_param("t_z")



        self.cup_n = 9
        self.buffer = tf2_ros.Buffer()
        self.listener = tf2_ros.TransformListener(self.buffer)

        self.cup_positions = []
        for i in range(self.cup_n+1):
            self.cup_positions.append(Pose())


    # Functions that add objects to scene
    def add_table(self,name,position, timeout=4):
        """Adds table object to planning scene
        """
        # add ctable surface 
        box_name = name
        box_pose = geometry_msgs.msg.PoseStamped()
        box_pose.header.frame_id = 'world'
        box_pose.pose.orientation.w = 1.0
        
        tablePos = self.gms("Table", "base").pose
        # rospy.loginfo(f"table pos = {tablePos}")
        box_pose.pose.position.x = tablePos.position.x
        box_pose.pose.position.y = tablePos.position.y
        box_pose.pose.position.z = tablePos.position.z
        box_pose.pose.position.x =  0.7
        box_pose.pose.position.y =  0.0
        box_pose.pose.position.z = -0.2
        self.scene.add_box(box_name, box_pose, size=(self.table_x, self.table_y, self.table_z))


        self.wait_for_state_update(object_name= "table", box_is_known=True, timeout=1)
        

    def add_cup(self,name, position, timeout=1):
        """Adds a cup object at a specified position
        Args:
            name (str): name of cup to place in scene (ex. cup3)
            posistion (????): postion of specified cup in planning scene
            timeout (int): we wait until updates have been made or "timeout" seconds have passed
        Returns: 
            True or False (bool): pending on result from wait_for_state_update
        """
        cylinder_pose = geometry_msgs.msg.PoseStamped()
        cylinder_pose.header.frame_id = 'world'
        cylinder_pose.pose.orientation.w = 1.0
        cylinder_pose.pose.position.x = position.x
        cylinder_pose.pose.position.y = position.y
        cylinder_pose.pose.position.z = position.z # if on first row height should be: self.cup_height/2.0 + self.table_z/2

        self.scene.add_cylinder(name,cylinder_pose,self.cup_height,self.cup_radius)
        return self.wait_for_state_update(object_name=name,box_is_known=True, timeout=1)

    

    def restart_scene_workStation(self):
        """Restarts gazebo scene """
        pose = Pose()
        twist = Twist()
        pose.position = Point(1,0.0,0.3)
        
        pose.position.y = 0
        self.sms(ModelState("Cup_1",pose,twist,"base"))
        pose.position.y = 0.4
        self.sms(ModelState("Cup_2",pose,twist,"base"))
        pose.position.y = -0.4
        self.sms(ModelState("Cup_3",pose,twist,"base"))

        self.create_scene()

    def restart_scene_inline(self):
        """restarts gazebo scene """
        pose = Pose()
        twist = Twist()
        pose.position = Point(0.8,0.8,0.1)
        
        self.sms(ModelState("Cup_1",pose,twist,"base"))
        pose.position.x = 1.2
        self.sms(ModelState("Cup_2",pose,twist,"base"))
        pose.position.y = -pose.position.y
        pose.position.x = 0.8
        self.sms(ModelState("Cup_3",pose,twist,"base"))

        self.create_scene() 


    def create_scene(self):
        """Creates scene at moveIt with 3 cups at the table
        """

        for i in range(self.cup_n):
            cup_name = "Cup_"+str(i+1)
            cupPos = self.gms(cup_name,"base").pose
            self.add_cup(cup_name,cupPos.position)

        table = self.gms("Table","base")
        self.add_table("Table",table.pose.position)
        ModelState("Table",table.pose,Twist(),"base")
    
    def set_table_posistion(self):
        """Adds table in rviz and gazebo at a position that
        is specifed in scene_objects.yaml
        """
        pose = Pose()
        twist = Twist()
        pose.position = Point(self.table_posx,self.table_posy,self.table_posz)
        self.sms(ModelState("Table",pose,twist,"base"))
        self.add_table("Table", pose.position)


    def wait_for_state_update(self, object_name ,box_is_known=False, box_is_attached=False, timeout=1):
        """Copied from tutorial
        """

        start = rospy.get_time()
        seconds = rospy.get_time()
        while (seconds - start < timeout) and not rospy.is_shutdown():
            # Test if the box is in attached objects
            attached_objects = self.scene.get_attached_objects([object_name])
            is_attached = len(attached_objects.keys()) > 0
            # Test if the box is in the scene.
            # Note that attaching the box will remove it from known_objects
            is_known = object_name in self.scene.get_known_object_names()
            # Test if we are in the expected state
            if (box_is_attached == is_attached) and (box_is_known == is_known):
                return True

            # Sleep so that we give other threads time on the processor
            rospy.sleep(0.1)
            seconds = rospy.get_time()

        # If we exited the while loop without returning then we timed out
        return False
        ## END_SUB_TUTORIAL



    # def attach_cup(self, ee_link, cup_name, robot,  timeout=4):
    def attach_cup(self, ee_link, robot,cup_name,  timeout=1):
        """Attaches objects to the robot.
        Adds link names to touch_links array. 
        This tells the planning scene to ignore collisons between the robot and 
        cups.
        Args:
             ee_link (str): name of end effector group name
             cup_name (str) : cup object to attach to robot
             robot (RobotComander object): provides info about robot
        """
        if(cup_name=="Cup_0"):
            return 0
        rospy.logdebug("attach : "+str(cup_name))
        # get a list of known objects in scene
        known_object_list = self.scene.get_known_object_names()
        if cup_name not in known_object_list:
            rospy.logerr("Object %s does not exist in the scene", cup_name)
            rospy.logerr(known_object_list)

        grasping_group = ee_link   # end effector group name
        touch_links = robot.get_link_names(group = grasping_group)
        # rospy.logerr(touch_links)
        
        self.scene.attach_mesh(ee_link, cup_name, touch_links = touch_links)   # attach mesh is a moveit commander function


        #wait for planning scene to update
        return self.wait_for_state_update(cup_name, box_is_attached=True, box_is_known=False, timeout=timeout)
      

    def detach_cup(self,cup_name,ee_link, timeout=1):
        """detach a cup from robot

        """
        # Copy class variables to local variables to make the web tutorials more clear.
        # In practice, you should use the class variables directly unless you have a good
        # reason not to.
        if(cup_name=="Cup_0"):
            return 0
        rospy.logdebug("detach :"+str(cup_name))
        self.scene.remove_attached_object(ee_link, name=cup_name)

        # We wait for the planning scene to update.
        return self.wait_for_state_update(cup_name,box_is_known=True, box_is_attached=False, timeout=timeout)


    def fake_sms(self, ModelState):
        pass

    def fake_gms(self, name,base):
        pos = Pose()
        if(name=="Table"):
            tagPos = self.listen_tag(1)
            pos.position.x= tagPos[0]
            pos.position.y= tagPos[1]
            pos.position.z= tagPos[2]
            rospy.loginfo(f"table tag = {tagPos}")
        else:
            id = int(name[-1])+1
            tagPos = self.listen_tag(id)
            pos.position.x= tagPos[0]
            pos.position.y= tagPos[1]
            pos.position.z= tagPos[2]

        if(name=="Table"):
            list_id = 0
        else:
            list_id = int(name[-1])

                
        if(pos.position.x !=0 and pos.position.y !=0 and pos.position.z !=0 ):
            self.cup_positions[list_id].position.x = pos.position.x
            self.cup_positions[list_id].position.y = pos.position.y
            self.cup_positions[list_id].position.z = pos.position.z

        return ModelState(name,self.cup_positions[list_id],Twist(), "base")
        # return ModelState(name,pos,Twist(), "base")

    def listen_tag(self, i):
        """ 
        Listens to the most recent end_effector's position with respect to the base_link. 
        """
        try:
            name = "tag_" + str(i)
            trans = self.buffer.lookup_transform('base', name, rospy.Time())
            # rospy.loginfo(f"{trans}")
            tagX = trans.transform.translation.x
            tagY = trans.transform.translation.y
            tagZ = trans.transform.translation.z
            # rospy.loginfo(f"({tagX}, {tagY}, {tagZ})")
            return (tagX, tagY, tagZ)
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            rospy.logerr(f"ERROR in listen_tag no lookup_transform found for {i}! ")
            return (0, 0, 0)




    def cups_sorted(self):
        """
        Returns True if all cups are inside inLine workspace 
        Returns False if any cup is still inside the workspace
        """
        cups_list = []
        for i in range(self.cup_n):
            cups_list.append("Cup_"+str(i+1))

        for cup in cups_list:
            position = self.get_cup_position(cup)
            y_pos = position.y
            # if the cup is in the middle two quadrants of the table
            if y_pos < self.table_y/4 and y_pos > -1*self.table_y/4:
                return False
        return True

    def assign_cup_st1(self,hand):
        """
        This function sorts cups that are randomly placed in the middle
        two quadrants of the table based on their x and y position.  
        - add hand as input later
        this function is for state 1 
        Return the position of a cup that should be grabed from hand arm
        left_hand arm gets y>0 
        right_hand arm gets y<0
        priority is given to cup with min(x)
        """
        dictio_left,dictio_right = self.create_dictionary("InWorkspace")
        if(hand=="left_gripper") and not len(dictio_left) == 0:
            cup_name = self.get_min_of_dict(dictio_left)

        elif(hand=="right_gripper") and not len(dictio_right) == 0:
            cup_name = self.get_min_of_dict(dictio_right)
        else:
            rospy.logerr("ERROR in assing_cup_st1 no hand recognised!")
            return "Cup_0"
        return cup_name
       


    def get_cup_position(self,name):
        """return the position of Cup
        """
        if(name=="Cup_0"):
            cup = Pose()
            cup.position.x = 0
            cup.position.y = 0
            cup.position.z = 0
            return cup.position
        cup = self.gms(name,"base")
        return cup.pose.position




    def create_dictionary(self,workspace):
        """
        creates 2 lists(sorted) for each arm that contain th cups position 
            Arg: 
                workspace --> InWorkspace or OutWorkspace choose to populate the list with cups that are in sorted WS or not
        """
        dictio_left = {}
        dictio_right = {}

        # get only sorted cups & split  left right lists
        condition = self.table_y/4.0
        for i in range(self.cup_n):
            k = i + 1
            cup_name = "Cup_"+str(k)
            cup_pos = self.gms(cup_name,"base").pose.position
            if(workspace=="OutWorkspace"):
                if(cup_pos.y>condition):
                    dictio_left[cup_name] = cup_pos
                elif(cup_pos.y<-1*condition):
                    dictio_right[cup_name]=cup_pos
            elif(workspace=="InWorkspace"):
                if cup_pos.y < condition and cup_pos.y > -1*condition:
                    if(cup_pos.y>0):
                        dictio_left[cup_name] = cup_pos
                    elif(cup_pos.y<0):
                        dictio_right[cup_name] = cup_pos

        #sort list with min(x) being the first
        return dictio_left,dictio_right


    def grab_next_cup(self,hand):
        """
        Return the cup_name  of the next cup that should be grabed from the sorting workspace
        """
        dictio_left,dictio_right = self.create_dictionary("OutWorkspace")
        if hand=="left_gripper" and not len(dictio_left)==0:
            cup_name = self.get_min_of_dict(dictio_left)

        elif hand=="right_gripper" and not len(dictio_right)==0:
            cup_name = self.get_min_of_dict(dictio_right)
        else:
            rospy.logerr("ERROR in grab_next_pos no hand recognised!")
            return "Cup_0"
        return cup_name

    def place_next_pos(self,hand):
        """
        Returns the position of the next cup that will be placed at the sorting workspace
        """
        dictio_left,dictio_right = self.create_dictionary("OutWorkspace")

        #handle expeption of first cup
        if(hand=="left_gripper" and len(dictio_left)==0):
            pos = Pose().position
            pos.x = 1.0
            pos.y = self.table_y/4.0 +0.2
            pos.z = self.table_posz + self.cup_height*2
            return pos

        if(hand=="right_gripper" and len(dictio_right)==0):
            pos = Pose().position
            pos.x = 1.0
            pos.y = -1*self.table_y/4.0 - 0.2
            pos.z = self.table_posz + self.cup_height*2
            return pos

        if(hand=="left_gripper"):
            diction = dictio_left
            
        elif(hand=="right_gripper"):
            diction = dictio_right
        else:
            rospy.logerr("ERROR in place_pos no hand recognised!")
            return Pose().position

        cup_name = self.get_min_of_dict(diction)
        pos = diction[cup_name]
        pos.x = pos.x - self.cup_radius*1.2
        return pos

    def get_max_of_dict(self,dictio):
        """ return the maximum key from dictionary based on position.x"""
        return [k for k,v in dictio.items() if v.x==max([val.x for val in dictio.values()])][0]

    def get_min_of_dict(self,dictio):
        """ return the minimum key from dictionary based on position.x"""
        return [k for k,v in dictio.items() if v.x==min([val.x for val in dictio.values()])][0]