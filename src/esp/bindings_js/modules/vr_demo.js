/* global VRFrameData */
import WebDemo from "./web_demo";
import { defaultResolution, defaultAgentConfig } from "./defaults";

class VRDemo extends WebDemo {
  normalSceneFrame;
  vrSceneFrame;
  canvasElement;
  fpsElement;
  lastPaintTime;
  frameData = new VRFrameData();
  previousRotation = false;
  previousPosition = false;
  currentVrDisplay = false;
  fps = 0;
  skipFrames = 60;
  currentFramesSkipped = 0;
  currentResolution = defaultResolution;

  constructor(canvasId = "canvas", fpsId = "fps") {
    super();
    this.canvasElement = document.getElementById(canvasId);
    this.fpsElement = document.getElementById(fpsId);
  }

  display() {
    this.setUpVR();
  }

  setUpVR() {
    navigator.getVRDisplays().then(displays => {
      if (displays.length > 0) {
        this.setupDisplay(displays[0]);
      } else {
        console.log("VR display not supported by this device");
        super.initializeModules();
        super.display();
      }
    });
  }

  setupDisplay(display) {
    this.currentVrDisplay = display;
    this.currentVrDisplay
      .requestPresent([
        {
          source: this.canvasElement
        }
      ])
      .then(() => this.setupCanvas())
      .then(() => this.initializeModules())
      .then(() => this.renderDisplay());
  }

  renderDisplay() {
    this.task.reset();
    this.drawVRScene();
  }

  setupCanvas() {
    const leftEye = this.currentVrDisplay.getEyeParameters("left");
    const rightEye = this.currentVrDisplay.getEyeParameters("right");

    const width = Math.max(leftEye.renderWidth, rightEye.renderWidth) * 2;
    const height = Math.max(leftEye.renderHeight, rightEye.renderHeight);
    this.currentResolution = { height, width };
    this.resetCanvas(this.currentResolution);
  }

  resetCanvas = resolution => {
    this.canvasElement.width = resolution.width;
    this.canvasElement.height = resolution.height;
  };

  /**
   * @override
   */
  updateAgentConfigWithSensors(agentConfig = defaultAgentConfig) {
    agentConfig = super.updateAgentConfigWithSensors(agentConfig);
    agentConfig = this.updateAgentConfigWithResolution(agentConfig);
    return agentConfig;
  }

  updateAgentConfigWithResolution(agentConfig) {
    agentConfig.sensorSpecifications.forEach(sensorConfig => {
      sensorConfig.resolution = [
        this.currentResolution.height,
        this.currentResolution.width
      ];
    });

    return agentConfig;
  }

  drawVRScene() {
    this.vrSceneFrame = this.currentVrDisplay.requestAnimationFrame(
      this.drawVRScene.bind(this)
    );
    this.currentVrDisplay.getFrameData(this.frameData);
    this.updateAgentState();
    this.task.render();
    this.currentVrDisplay.submitFrame();
    this.updateFPS();
  }

  updateAgentState() {
    const agent = this.simenv.sim.getAgent(this.simenv.selectedAgentId);
    let prevAgentState = this.simenv.createAgentState({});
    agent.getState(prevAgentState);

    const simRotation = prevAgentState.rotation.slice();
    const simPosition = prevAgentState.position.slice();

    if (!this.previousRotation) {
      this.previousRotation = this.frameData.pose.orientation.slice();
      this.previousPosition = this.frameData.pose.position.slice();
    } else {
      const poseRotation = this.frameData.pose.orientation;
      const posePosition = this.frameData.pose.position;

      poseRotation.forEach((item, index) => {
        simRotation[index] += item - this.previousRotation[index];
      });
      posePosition.forEach((item, index) => {
        simPosition[index] += item - this.previousPosition[index];
      });
      this.previousRotation = poseRotation.slice();
      this.previousPosition = posePosition.slice();
    }
    let agentState = { position: simPosition, rotation: simRotation };
    agentState = this.simenv.createAgentState(agentState);

    agent.setState(agentState, true);
  }

  updateFPS() {
    if (this.currentFramesSkipped != this.skipFrames) {
      this.currentFramesSkipped++;
      return;
    }

    this.currentFramesSkipped = 0;

    if (!this.lastPaintTime) {
      this.lastPaintTime = performance.now();
    } else {
      const current = performance.now();
      const secondsElapsed = (current - this.lastPaintTime) / 1000;
      this.fps = this.skipFrames / secondsElapsed;
      this.lastPaintTime = current;
      this.fpsElement.innerHTML = `FPS: ${this.fps.toFixed(2)}`;
    }
  }
}

export default VRDemo;
