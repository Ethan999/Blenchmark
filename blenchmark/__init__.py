# ##### BEGIN GPL LICENSE BLOCK #####

#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {  
 "name": "BlenchMark",  
 "author": "Mark aka Dark (MAD)",  
 "version": (1, 0, 5),  
 "blender": (2, 74, 0),  
 "location": "Render > BenchMark",  
 "description": "Runs a benchmark scene and uploads renderstatistics",  
 "warning": "",  
 "wiki_url": "http://www.mad-creations.nl/blenchmark/article/benchmark-your-cpu-or-gpu",  
 "tracker_url": "http://www.mad-creations.nl/blenchmark/issue-overview",  
 "category": "System"} 

if "bpy" in locals():
    import imp
    imp.reload(cpuinfo)
else:
    from . import cpuinfo

    
import bpy, bgl, time, inspect, platform, xmlrpc.client, urllib.request, hashlib, os.path
from datetime import timedelta
from bpy.props import *

class BMCookieTransport(xmlrpc.client.Transport):
    def send_content(self, connection, request_body):
        if hasattr(self,'cookiename'):
            connection.putheader('Cookie', "%s=%s" % (self.cookiename, self.cookievalue))
            if hasattr(self,'token'):
                connection.putheader('X-CSRF-Token', "%s" % (self.token))
        return xmlrpc.client.Transport.send_content(self, connection, request_body)

class BenchMarkOperator(bpy.types.Operator):
    bl_idname = "object.benchmark_operator"
    bl_label = "BenchMark"
    
    def execute(self, context):
        global autotilesizeison
        if autotilesizeison:
            bpy.ops.wm.addon_disable(module="render_auto_tile_size")
            autotilesizeison = False
        blendpath = inspect.getfile(inspect.currentframe())[0:-len("__init__.py")] + "BlenchMarkSceneV3.blend"    
        bpy.ops.wm.open_mainfile(filepath=blendpath)
        global RenderTime
        global isaltered
        RenderTime = ""
        isaltered = False
        try:
            bpy.utils.register_class(BenchMarkPanel)
        except:
            pass
        try:
            bpy.utils.register_class(DialogOperator)
        except:
            pass
        try:
            bpy.app.handlers.load_pre.append(delete_BMPanel)
        except:
            pass
        try:
            bpy.app.handlers.render_pre.append(start_timer)
        except:
            pass
        try:
            bpy.app.handlers.render_complete.append(end_timer)
        except:
            pass          
        return {'FINISHED'}

class MessageOperator(bpy.types.Operator):
    bl_idname = "error.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
    
    global autotilesizeison
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        global autotilesizeison
        global currentversion
        try:
            currentversion = str(bl_info["version"][0]) + "." + str(bl_info["version"][1]) + "." + str(bl_info["version"][2])
            latestversion = urllib.request.urlopen('https://dl.dropboxusercontent.com/u/43534527/Blenchmark/version.txt')
            latestversion = latestversion.read()
            latestversion = latestversion.decode("utf-8")
            print(latestversion)
            print(currentversion)
            versioniscurrent = (latestversion == currentversion)
        except:
            versioniscurrent = True
            
        if 'render_auto_tile_size' in bpy.context.user_preferences.addons.keys():
            autotilesizeison = True
        else:
            autotilesizeison = False
        
        if versioniscurrent is False:
            print(versioniscurrent)
            bpy.ops.oldversion.message('INVOKE_DEFAULT')
            bpy.ops.wm.addon_disable(module="blenchmark")
            return {'FINISHED'}
        else:
            wm = context.window_manager
            return wm.invoke_popup(self, width=500, height=200)
 
    def draw(self, context):
        global autotilesizeison
        layout = self.layout
        layout.label("WARNING", icon='ERROR')
        row = layout.row()
        row.label("When you start this benchmark your current scene wil be closed without saving.")
        if autotilesizeison:
            row = layout.row()
            row.label(text="you have the Auto Tile Size addon enabled, this addon wil be disabled.")
        row = layout.row()
        row.label("Do you want to proceed?")
        row = layout.row()
        row.operator("error.cancel")
        row.operator("error.ok")
        #return {'FINISHED'}

class OkOperator(bpy.types.Operator):
    bl_idname = "error.ok"
    bl_label = "Run BenchMark now!"
    global autotilesizeison
    def execute(self, context):
        bpy.ops.object.benchmark_operator()
        return {'FINISHED'}
    
class CancelOperator(bpy.types.Operator):
    bl_idname = "error.cancel"
    bl_label = "No! (press ESC)"
    def execute(self, context):
        return {'FINISHED'}

class BenchMarkPanel(bpy.types.Panel):
    bl_idname = "BMpanel"
    bl_label = "Benchmark"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    
    global RStatus 
    RStatus = "Unfinished"
    
    def draw(self, context):
        import sys
        layout = self.layout
        scene = context.scene
        
        userpref = context.user_preferences
        system = userpref.system

        row = layout.row()
        split = layout.split()
        column = split.column()
        colsplit = column.split(percentage=1)

        col = colsplit.column()
        row.operator("object.render_bmrender_operator", text="Start Benchmark")
        row.operator("object.dialog_operator", text="Show Results")
        row.operator("object.bm_sentres_operator", text="Send Results")
        
        if scene.render.engine == 'CYCLES':
            #from . import engine
            cscene = scene.cycles

            device_type = context.user_preferences.system.compute_device_type
            if device_type in {'CUDA', 'OPENCL'}:
                layout.prop(cscene, "device")
        
        if hasattr(system, "compute_device_type"):
            col.label(text="Compute Device:")
            col.row().prop(system, "compute_device_type", expand=True)
            sub = col.row()
            sub.active = system.compute_device_type != 'CPU'
            sub.prop(system, "compute_device", text="")

class Oldversion_MessageOperator(bpy.types.Operator):
    bl_idname = "oldversion.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=200)
 
    def draw(self, context):
        layout = self.layout
        layout.label("Newer version available!", icon='ERROR')
        row = layout.row()
        row.label("There is a newer version of this addon available.")
        row = layout.row()
        row.label("This addon will be disabled. Please install the new version!")
        
class diffcards_MessageOperator(bpy.types.Operator):
    bl_idname = "diffcards.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=200)
 
    def draw(self, context):
        layout = self.layout
        layout.label("You are using different gpu's!", icon='ERROR')
        row = layout.row()
        row.label("You are using different gpu's.")
        row = layout.row()
        row.label("Run this benchmark with identical cards only!")
        
class addonison_MessageOperator(bpy.types.Operator):
    bl_idname = "addonison.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=200)
 
    def draw(self, context):
        layout = self.layout
        layout.label("Auto Tile Size addon is enabled!", icon='ERROR')
        row = layout.row()
        row.label("Don't mess up the results and disable this addon!")

class SR_MessageOperator(bpy.types.Operator):
    bl_idname = "sr_error.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=200)
 
    def draw(self, context):
        layout = self.layout
        layout.label("WARNING", icon='ERROR')
        row = layout.row()
        row.label("Something went wrong while uploading the benchmark!")
        row = layout.row()
        row.label("Possible reasons:")
        row = layout.row()
        row.label("- No internet-connection;")
        row = layout.row()
        row.label("- Blenchmark.com is down;")
        row = layout.row()
        row.label("- Old add-on version.")
        row = layout.row()
        row.label("Visit Blenchmark.com for assistance.")

class Md5WrongOperator(bpy.types.Operator):
    bl_idname = "md5wrong.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=200)
 
    def draw(self, context):
        layout = self.layout
        layout.label("WARNING", icon='ERROR')
        row = layout.row()
        row.label("You somehow changed and saved the benchmark-scene")
        row = layout.row()
        row.label("copy the blend file from the download or")
        row = layout.row()
        row.label("reinstall the addon")
        row = layout.row()
        row.label("Visit Blenchmark.com for assistance.")

class ReloadOkOperator(bpy.types.Operator):
    bl_idname = "reload.ok"
    bl_label = "Reload!"
    global autotilesizeison
    def execute(self, context):
        bpy.ops.wm.revert_mainfile()
        bpy.utils.register_class(BenchMarkPanel)
        bpy.app.handlers.load_pre.append(delete_BMPanel)
        bpy.app.handlers.render_pre.append(start_timer)
        bpy.app.handlers.render_complete.append(end_timer)
        return {'FINISHED'}
        
class ReloadSceneOperator(bpy.types.Operator):
    bl_idname = "reload_scene.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        
        if 'render_auto_tile_size' in bpy.context.user_preferences.addons.keys():
            autotilesizeison = True
        else:
            autotilesizeison = False

        wm = context.window_manager
        return wm.invoke_popup(self, width=250, height=200)
 
    def draw(self, context):
        global autotilesizeison
        layout = self.layout
        layout.label("WARNING", icon='ERROR')
        row = layout.row()
        row.label("This scene is altered and will be reloaded.")
        row = layout.row()
        row.label("After reload hit benchmark again")
        row = layout.row()
        row.operator("reload.ok")
        #return {'FINISHED'}
        
class SROK_MessageOperator(bpy.types.Operator):
    bl_idname = "sr_ok.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=200)
 
    def draw(self, context):
        layout = self.layout
        layout.label("Upload done", icon='INFO')
        row = layout.row()
        row.label("Uploading your results has finished")
        row = layout.row()
        row.label("Visit Blenchmark.com for results.")

#Start render button in panel
class BMRenderOperator(bpy.types.Operator):
    bl_idname = "object.render_bmrender_operator"
    bl_label = "Define Renderer"
    
    def execute(self, context):
        global BMRender
        global autotilesizeison
        global RStatus
        global gpu_or_cpu
        global isaltered
        
        blendpath = inspect.getfile(inspect.currentframe())[0:-len("__init__.py")] + "BlenchMarkSceneV3.blend"
        hashsha1 = hashlib.sha1()
        with open(blendpath, 'rb') as dotblend:
            buffer = dotblend.read()
            hashsha1.update(buffer)
        dotblendhash = hashsha1.hexdigest()
        if dotblendhash != "0e28268f196d97049ae33da980231f063ab44102":
            bpy.ops.md5wrong.message('INVOKE_DEFAULT')
            isaltered = True
        else:
            print("hash checks out well")
            if isaltered:
                isaltered = False
                bpy.ops.reload_scene.message('INVOKE_DEFAULT')
            else:
                dirty = bpy.data.is_dirty;
                if dirty:
                    bpy.ops.reload_scene.message('INVOKE_DEFAULT')
                    print("is_dirty")
                else:
                    if 'render_auto_tile_size' in bpy.context.user_preferences.addons.keys():
                        bpy.ops.addonison.message('INVOKE_DEFAULT')
                    else:
                        if bpy.context.scene.cycles.device == 'CPU':
                            gpu_or_cpu = "CPU"
                            render = cpuinfo.get_cpu_info()
                            BMRender = render['brand']
                        if bpy.context.scene.cycles.device == 'GPU':
                            gpu_or_cpu = "GPU"
                            system = bpy.context.user_preferences.system
                            prop = bpy.context.user_preferences.system.rna_type.properties["compute_device"]
                            BMRender = prop.enum_items[system.compute_device].name
                            BMRender = BMRender.replace('/', '|')
                        
                        if context.user_preferences.system.compute_device_type == 'NONE':
                            render = cpuinfo.get_cpu_info()
                            BMRender = render['brand']
                            gpu_or_cpu = "CPU"
                        if '+' in BMRender:
                            bpy.ops.diffcards.message('INVOKE_DEFAULT')
                        else:
                            bpy.data.scenes["Scene"].render.tile_x = 128
                            bpy.data.scenes["Scene"].render.tile_y = 64
                            RStatus = "Unfinished"
                            bpy.ops.render.render('INVOKE_DEFAULT')
        return {'FINISHED'}
            
        
class BMSentResultsOperator(bpy.types.Operator):
    bl_idname = "object.bm_sentres_operator"
    bl_label = "Send Results"
    
    def execute(self, context):
        global BMRender, RenderTime, opsys, version, currentversion, gpu_or_cpu
        if RStatus == "Finished":
            try:
                transport = BMCookieTransport()
                url = "http://blenchmark.com/anonymus/benchmarks"
                uname = 'Blender'
                passwd = 'Blender00'
                proxy = xmlrpc.client.ServerProxy(url, transport, verbose=True)
                login = proxy.user.login(uname,passwd)
                transport.cookievalue=login['sessid']
                transport.cookiename=login['session_name']
                transport.token = login['token']
                
                connect = proxy.system.connect()
                
                new_benchmark={
                               'type': 'benchmark',
                               'comment': '1',
                               'title': BMRender,
                               #'field_device': {'und': [{'format': '', 'value': 'Nvidia'}]}, 
                               'field_operating_system':{'und': [{'format': '', 'value': opsys}]},
                               'field_blender_version':{'und': [{'format': '', 'value': version}]}, 
                               'field_render_time': {'und': [{'format': '', 'value': RenderTime}]},
                               'field_addon_version': {'und':[{'format': '', 'value': currentversion}]},
                               'field_type': {'und':[{'format': '', 'value': gpu_or_cpu}]},
                               'field_ip': {'und': [{'format': '', 'value': connect['user']['hostname']}]}
                               }
                bmresult = proxy.benchmarks.create(new_benchmark)
                bpy.ops.sr_ok.message('INVOKE_DEFAULT')
            except:
                bpy.ops.sr_error.message('INVOKE_DEFAULT')
        return {'FINISHED'}
    
class DialogOperator(bpy.types.Operator):
    bl_idname = "object.dialog_operator"
    bl_label = "BenchMark Results"
    
    my_os = StringProperty(name="Operating System")
    my_bversion = StringProperty(name="Blender version")
    my_device = StringProperty(name="Render Device")
    my_time = StringProperty(name="Render Time")
 
    def execute(self, context):
        message = "%s, %s, '%s' %s" % (self.my_os, 
            self.my_bversion, self.my_device, self.my_time)
        self.report({'INFO'}, message)
        print(message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        global RStatus
        if RStatus == "Finished":
            global BMRender, RenderTime, opsys, version
            self.my_os = opsys
            self.my_bversion = version
            self.my_device = BMRender
            self.my_time = RenderTime
            return context.window_manager.invoke_props_dialog(self)
        return {'FINISHED'}
    
    
def start_timer(scene):
    global timer
    global time_start
    
    if scene.frame_current == scene.frame_start:
        timer = {"total": 0.0}

    time_start = time.time()

def end_timer(scene):
    global timer
    global time_start
    global BMRender
    global RenderTime
    global opsys
    global version
    global RStatus
    
    print("timerend")
    RStatus = "Finished"
    render_time = time.time() - time_start
    timer["total"] += render_time
    RenderTime = str(timedelta(seconds = timer["total"]))
    RenderTime = RenderTime.replace(' ', '')[:-7]
    print(RenderTime)
    print(BMRender)
    system = platform.system()
    release = platform.release()
    arch = platform.architecture()[0]
    if system == "Linux":
        opsys = platform.dist()[0] + " " + platform.dist()[1] + " " + arch
    elif system == "Darwin":
        opsys = "Mac OS " + platform.mac_ver()[0] + " " + arch
    elif system == "Windows":
        opsys = opsys = system + " " + release + " " + arch
    else:
        opsys = "Not known"
    print(opsys)
    subversion = bpy.app.version[2]
    if subversion == 0:
        subversion = ""
    else:
        subversion = "." + str(subversion)
            
    char = bpy.app.version_char
    version = str(bpy.app.version[0]) + "." + str(bpy.app.version[1]) + subversion + char
    print(version)
    
    #bpy.ops.object.dialog_operator('INVOKE_DEFAULT')

    
    
def add_object_button(self, context):  
    self.layout.operator(  
        MessageOperator.bl_idname,  
        "BenchMark",  
        icon='PLUGIN')

def delete_BMPanel(context):
    bpy.utils.unregister_class(bpy.types.BMpanel)
    bpy.utils.unregister_class(bpy.ops.object.dialog_operator)
    bpy.app.handlers.render_pre.remove(start_timer)
    bpy.app.handlers.render_complete.remove(end_timer)
    bpy.app.handlers.load_pre.remove(delete_BMPanel)
     
classes = [MessageOperator, BenchMarkOperator, OkOperator, CancelOperator, BMRenderOperator, Oldversion_MessageOperator]
         
def register():
    bpy.utils.register_module(__name__)
    bpy.utils.unregister_class(bpy.types.BMpanel)
    bpy.utils.unregister_class(DialogOperator)
      
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except:
            pass
            
    bpy.types.INFO_MT_render.append(add_object_button)
    
def unregister():
    bpy.utils.unregister_module(__name__)
    
    for c in classes:
        try:
            bpy.utils.unregister_class(c)
        except:
            pass
    try:
        bpy.types.INFO_MT_render.remove(add_object_button)
    except:
        pass
    try:
        bpy.app.handlers.render_pre.remove(start_timer)
    except:
        pass
    try:
        bpy.app.handlers.render_complete.remove(end_timer)
    except:
        pass
    try:
        bpy.app.handlers.load_pre.remove(delete_BMPanel) 
    except:
        pass
    try:
        bpy.utils.unregister_class(bpy.types.BMpanel)
    except:
        pass
    
if __name__ == "__main__":  
    register()  