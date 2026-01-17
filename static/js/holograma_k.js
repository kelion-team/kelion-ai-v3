import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { FXAAShader } from "three/addons/shaders/FXAAShader.js";

export class HologramUnit {
  constructor(containerId, onProgress = () => { }) {
    this.container = document.getElementById(containerId);
    this.onProgress = onProgress;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100); // 35mm lens for more cinematic look
    this.camera.position.set(0, 0, 1.8); // Adjust distance for new lens

    this.renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: "high-performance" });
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2; // Slightly brighter
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;

    this.clock = new THREE.Clock();
    // Force resize after slight delay to ensure container has size
    setTimeout(() => {
      this.resize();
      if (this.modelRoot) this.modelRoot.position.set(0, -0.9, 0); // Lower it a bit more
    }, 500);
    this.mixer = null;
    this.modelRoot = null;
    this.animations = [];
    this.actions = {}; // Use plain object instead of Map for consistency 
    this.currentAction = null;

    // lip sync
    this.audioEl = null;
    this.audioCtx = null;
    this.analyser = null;
    this.dataArray = null;
    this.jawBone = null;
    this.eyeBones = [];
    this.blinkTimer = 0;
    this.nextBlink = 2 + Math.random() * 4;
    this.idlePhase = 0;
    this.breathPhase = 0;
    this.morphTargets = [];
    this.visemeTargets = new Map();
    this.visemeTimeline = null;
    this.visemeIndex = 0;

    this.composer = null;

    // State for behavior - matches backend structure
    this.isFocused = false;
    this.lookTarget = new THREE.Vector2(0, 0); // Where it's looking
    this.lookPhase = 0;

    // Natural eye movement
    this.eyeLookTarget = new THREE.Vector2(0, 0);   // Current eye look direction
    this.eyeLookCurrent = new THREE.Vector2(0, 0); // Interpolated position
    this.nextEyeMove = 1 + Math.random() * 2;      // Time until next eye movement
    this.eyeMoveTimer = 0;

    // Backend sends: animation (idle/speak/happy/empathetic) + emotion (calm/happy/empathetic)
    this.params = {
      state: 'idle',      // current animation state
      emotion: 'calm',    // current emotion from backend
      isSpeaking: false,  // is TTS audio playing
      isListening: false  // user is providing input (stops hologram movement)
    };
    // Timer for returning to idle after inactivity (2 minutes)
    this.lastActivityTime = Date.now();
    this.idleTimeout = 2 * 60 * 1000; // 2 minutes in milliseconds
  }

  init() {
    this.setupScene();
    this.setupRenderer();
    this.loadResources();
    window.addEventListener("resize", () => this.resize());
    this.resize();
    this.animate();
  }

  setupScene() {
    // === PREMIUM STUDIO LIGHTING FOR PHOTOREALISTIC SKIN ===

    // Soft ambient - simulates bounce light in studio
    this.scene.add(new THREE.AmbientLight(0xfff5ee, 0.4));

    // Hemisphere light for natural sky/ground gradient
    const hemi = new THREE.HemisphereLight(0xfff8f0, 0xd4a574, 0.6);
    this.scene.add(hemi);

    // KEY LIGHT - Main light source (5500K daylight)
    const key = new THREE.DirectionalLight(0xfffaf5, 2.8);
    key.position.set(1.5, 2, 3);
    key.castShadow = true;
    key.shadow.mapSize.width = 2048;
    key.shadow.mapSize.height = 2048;
    key.shadow.bias = -0.0001;
    this.scene.add(key);

    // FILL LIGHT - Softer, from opposite side (warmer)
    const fill = new THREE.DirectionalLight(0xffeedd, 1.2);
    fill.position.set(-2, 0.5, 2);
    this.scene.add(fill);

    // RIM/HAIR LIGHT - Creates separation from background
    const rim = new THREE.DirectionalLight(0xfff0e6, 1.8);
    rim.position.set(0, 2.5, -2);
    this.scene.add(rim);

    // CATCHLIGHT - Small bright light for eye sparkle
    const catchlight = new THREE.PointLight(0xffffff, 0.8, 5);
    catchlight.position.set(0.3, 0.5, 2);
    this.scene.add(catchlight);

    // UNDER CHIN FILL - Eliminates harsh shadows
    const chinFill = new THREE.DirectionalLight(0xffeae0, 0.5);
    chinFill.position.set(0, -1.5, 1.5);
    this.scene.add(chinFill);

    // CHEEK ACCENT - Subtle warmth on cheeks
    const cheekLeft = new THREE.PointLight(0xffddcc, 0.3, 3);
    cheekLeft.position.set(-1, 0, 1.5);
    this.scene.add(cheekLeft);

    const cheekRight = new THREE.PointLight(0xffddcc, 0.3, 3);
    cheekRight.position.set(1, 0, 1.5);
    this.scene.add(cheekRight);
  }

  setupRenderer() {
    this.renderer.setClearColor(0x000000, 0); // Transparent background

    // === CINEMATIC TONE MAPPING FOR PHOTOREALISTIC SKIN ===
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.composer = new EffectComposer(this.renderer);
    this.composer.setPixelRatio(this.renderer.getPixelRatio());

    const renderPass = new RenderPass(this.scene, this.camera);
    renderPass.clear = true;
    renderPass.clearAlpha = 0;
    this.composer.addPass(renderPass);

    // Subtle bloom - just for soft skin glow, not holographic
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(this.container.clientWidth, this.container.clientHeight),
      0.15, // Very subtle strength for realistic skin
      0.5,  // radius
      0.95  // high threshold - only brightest highlights bloom
    );
    this.composer.addPass(bloomPass);

    // FXAA Anti-aliasing - last pass
    const fxaaPass = new ShaderPass(FXAAShader);
    const pixelRatio = this.renderer.getPixelRatio();
    fxaaPass.material.uniforms['resolution'].value.x = 1 / (this.container.clientWidth * pixelRatio);
    fxaaPass.material.uniforms['resolution'].value.y = 1 / (this.container.clientHeight * pixelRatio);
    fxaaPass.renderToScreen = true; // CRITICAL: Ensure final pass renders to canvas
    this.composer.addPass(fxaaPass);
  }

  loadResources() {
    const loader = new GLTFLoader();
    console.log("Loading hologram from ./assets/hologram.glb ...");

    loader.load(
      "/assets/hologram.glb",
      (gltf) => {
        const model = gltf.scene;
        this.modelRoot = model;
        console.log("Model loaded!", model);

        // MATERIAL MANIPULATION - PHOTOREALISTIC SKIN + CRYSTALLINE EYES
        model.traverse((child) => {
          if (child.isMesh) {
            if (child.material) {
              const meshName = child.name.toLowerCase();
              const matName = child.material.name ? child.material.name.toLowerCase() : '';

              // Detect if this is any eye mesh
              const isEye = meshName.includes('eye') || matName.includes('eye') ||
                meshName.includes('iris') || matName.includes('iris');

              let finalMaterial;

              if (isEye) {
                // === REALISTIC EYE SHADER: Vibrant iris + catchlights + radial fibers ===
                finalMaterial = new THREE.ShaderMaterial({
                  uniforms: {
                    irisColor1: { value: new THREE.Color(0x2a7a6a) },     // Bright teal-green
                    irisColor2: { value: new THREE.Color(0x155545) },     // Darker green for depth
                    irisHighlight: { value: new THREE.Color(0x4ad4bc) },  // Bright cyan highlight
                    scleraColor: { value: new THREE.Color(0xfaf8f5) },    // Clean off-white
                    pupilColor: { value: new THREE.Color(0x050505) },     // Near-black pupil
                    irisRadius: { value: 0.42 },                          // Larger iris
                    pupilRadius: { value: 0.12 },                         // Smaller pupil - more human
                    limbusRing: { value: new THREE.Color(0x1a3530) },     // Dark ring around iris
                    time: { value: 0 }
                  },
                  vertexShader: `
                    varying vec2 vUv;
                    varying vec3 vNormal;
                    varying vec3 vViewPosition;
                    varying vec3 vWorldPos;
                    void main() {
                      vUv = uv;
                      vNormal = normalize(normalMatrix * normal);
                      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                      vViewPosition = -mvPosition.xyz;
                      vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
                      gl_Position = projectionMatrix * mvPosition;
                    }
                  `,
                  fragmentShader: `
                    uniform vec3 irisColor1;
                    uniform vec3 irisColor2;
                    uniform vec3 irisHighlight;
                    uniform vec3 scleraColor;
                    uniform vec3 pupilColor;
                    uniform vec3 limbusRing;
                    uniform float irisRadius;
                    uniform float pupilRadius;
                    uniform float time;
                    
                    varying vec2 vUv;
                    varying vec3 vNormal;
                    varying vec3 vViewPosition;
                    varying vec3 vWorldPos;
                    
                    // Noise function for iris texture
                    float hash(vec2 p) {
                      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
                    }
                    
                    void main() {
                      vec2 centered = vUv - vec2(0.5, 0.5);
                      float dist = length(centered);
                      float angle = atan(centered.y, centered.x);
                      
                      vec3 finalColor;
                      float alpha = 1.0;
                      
                      // === PUPIL - small, round, deep black ===
                      if (dist < pupilRadius) {
                        finalColor = pupilColor;
                        // Subtle depth gradient in pupil
                        float pupilGrad = dist / pupilRadius;
                        finalColor = mix(vec3(0.02), pupilColor, pupilGrad * 0.3);
                      }
                      // === IRIS with radial fibers and color variation ===
                      else if (dist < irisRadius) {
                        float irisT = (dist - pupilRadius) / (irisRadius - pupilRadius);
                        
                        // Radial fiber pattern
                        float fibers = sin(angle * 40.0) * 0.5 + 0.5;
                        fibers *= sin(angle * 23.0 + 1.5) * 0.5 + 0.5;
                        fibers = pow(fibers, 0.7);
                        
                        // Add some noise variation
                        float noise = hash(vec2(angle * 10.0, dist * 20.0)) * 0.15;
                        
                        // Base iris color with radial gradient (lighter near pupil)
                        vec3 baseIris = mix(irisColor1 * 1.4, irisColor2, irisT);
                        
                        // Apply fiber pattern
                        finalColor = mix(baseIris, irisHighlight, fibers * 0.25 * (1.0 - irisT));
                        finalColor += noise * 0.1;
                        
                        // Collarette ring (brighter ring around pupil)
                        float collarette = smoothstep(0.0, 0.3, irisT) * smoothstep(0.5, 0.3, irisT);
                        finalColor = mix(finalColor, irisHighlight * 0.9, collarette * 0.4);
                        
                        // Limbus ring (dark edge of iris)
                        float limbusEdge = smoothstep(0.85, 1.0, irisT);
                        finalColor = mix(finalColor, limbusRing, limbusEdge * 0.7);
                        
                        // Inner glow near pupil
                        float innerGlow = 1.0 - smoothstep(0.0, 0.4, irisT);
                        finalColor += irisHighlight * innerGlow * 0.2;
                      }
                      // === SCLERA (white of eye) ===
                      else {
                        finalColor = scleraColor;
                        // Subtle pink/vein tint at edges
                        float edgeFade = smoothstep(irisRadius, 0.55, dist);
                        vec3 veinTint = vec3(0.98, 0.92, 0.92);
                        finalColor = mix(finalColor, veinTint, edgeFade * 0.35);
                        
                        // Slight shadow near iris edge
                        float irisEdgeShadow = 1.0 - smoothstep(irisRadius, irisRadius + 0.05, dist);
                        finalColor *= 1.0 - irisEdgeShadow * 0.15;
                      }
                      
                      // === LIGHTING ===
                      vec3 lightDir = normalize(vec3(0.4, 0.6, 1.0));
                      float diffuse = max(dot(vNormal, lightDir), 0.4);
                      
                      // Specular for wet eye look
                      vec3 viewDir = normalize(vViewPosition);
                      vec3 halfDir = normalize(lightDir + viewDir);
                      float spec = pow(max(dot(vNormal, halfDir), 0.0), 128.0);
                      
                      // === CATCHLIGHTS - bright white reflection spots ===
                      // Primary catchlight (top-right)
                      vec2 catch1Pos = vec2(0.18, 0.22);
                      float catch1Dist = length(centered - catch1Pos);
                      float catchlight1 = smoothstep(0.08, 0.02, catch1Dist);
                      
                      // Secondary smaller catchlight (bottom-left, softer)
                      vec2 catch2Pos = vec2(-0.12, -0.1);
                      float catch2Dist = length(centered - catch2Pos);
                      float catchlight2 = smoothstep(0.05, 0.01, catch2Dist) * 0.5;
                      
                      // Combine catchlights
                      float totalCatchlight = min(1.0, catchlight1 + catchlight2);
                      
                      // Apply lighting
                      finalColor = finalColor * diffuse;
                      finalColor += vec3(1.0) * spec * 0.4;
                      
                      // Add catchlights on top (they're reflections, so very bright)
                      finalColor = mix(finalColor, vec3(1.0, 1.0, 0.98), totalCatchlight * 0.95);
                      
                      // Final subtle ambient occlusion at very edge of eye
                      float ao = smoothstep(0.5, 0.45, dist);
                      finalColor *= 0.85 + ao * 0.15;
                      
                      gl_FragColor = vec4(finalColor, alpha);
                    }
                  `,
                  side: THREE.DoubleSide,
                  transparent: true
                });

                // Store reference for animation updates
                child.userData.eyeShader = finalMaterial;
                console.log('Applied CRYSTALLINE EYE SHADER to:', child.name);
              } else {
                // === PHOTOREALISTIC SKIN MATERIAL ===
                finalMaterial = new THREE.MeshPhysicalMaterial({
                  color: new THREE.Color(0xe8c4a8),           // Realistic skin base
                  emissive: new THREE.Color(0x1a0a05),        // Very subtle warm glow
                  emissiveIntensity: 0.05,                    // Minimal emission

                  // Subsurface scattering for skin translucency
                  thickness: 0.8,
                  transmission: 0.0,

                  // Skin surface properties
                  metalness: 0.0,
                  roughness: 0.45,

                  // Sheen for skin micro-velvet effect
                  sheen: 0.25,
                  sheenRoughness: 0.4,
                  sheenColor: new THREE.Color(0xffccbb),

                  // Clearcoat for oily skin highlight areas
                  clearcoat: 0.1,
                  clearcoatRoughness: 0.3,

                  // Rendering
                  transparent: true,
                  opacity: 1.0,
                  side: THREE.DoubleSide,
                  envMapIntensity: 0.4,
                  flatShading: false
                });
              }

              // Preserve morphTargetInfluences if they exist
              if (child.morphTargetInfluences) {
                finalMaterial.morphTargets = true;
              }
              if (child.material.map && !isEye) {
                // Keep the texture for skin, not for eyes
                finalMaterial.map = child.material.map;
              }

              child.material = finalMaterial;
              child.material.needsUpdate = true;
            }
          }
        });

        // POSITION & SCALE
        // "incarca 145" -> Assuming Scale 1.45 or specific styling
        model.position.set(0, -1.2, 0); // Lower it to fit larger scale
        model.scale.set(1.45, 1.45, 1.45);

        this.scene.add(model);

        // ANIMATIONS
        this.mixer = new THREE.AnimationMixer(model);
        const clips = gltf.animations;
        if (clips && clips.length) {
          clips.forEach(clip => {
            const action = this.mixer.clipAction(clip);
            action.clampWhenFinished = false;
            action.loop = THREE.LoopRepeat;

            if (!this.actions) this.actions = {};
            this.actions[clip.name.toLowerCase()] = action;

            // Play idle by default if found
            if (clip.name.toLowerCase().includes('idle')) {
              action.play();
            }
          });
          // Fallback play first if no idle found specific
          if (Object.keys(this.actions || {}).length > 0 && !this.mixer.existingAction) {
            // play first available
            const firstKey = Object.keys(this.actions)[0];
            this.actions[firstKey].play();
          }
        }

        // Find jaw bone + morph targets for lip sync
        model.traverse((o) => {
          if (o.isBone && /jaw/i.test(o.name)) this.jawBone = o;
          if (o.isBone && /eye/i.test(o.name)) this.eyeBones.push(o);
          if (o.isMesh && o.morphTargetInfluences && o.morphTargetDictionary) {
            // pick mouth-related morph targets
            const keys = Object.keys(o.morphTargetDictionary);
            for (const k of keys) {
              if (/mouth|jaw|lip|viseme/i.test(k)) {
                this.morphTargets.push({ mesh: o, key: k, idx: o.morphTargetDictionary[k] });
              }
              // Viseme naming variants
              const lk = k.toLowerCase();
              const map = {
                "AA": ["viseme_aa", "visemeaa", "aa"],
                "EE": ["viseme_ee", "visemeee", "ee", "ih", "iy"],
                "OO": ["viseme_oo", "visemeoo", "oo", "uw"],
                "FV": ["viseme_fv", "visemefv", "fv"],
                "MBP": ["viseme_mbp", "visemembp", "mbp", "bmp", "pp", "mm"],
                "TH": ["viseme_th", "visemeth", "th", "dh"],
                "CH": ["viseme_ch", "visemech", "ch", "sh", "jh", "zh"],
                "KG": ["viseme_kg", "visemekg", "kg", "kk", "gg"],
                "S": ["viseme_s", "visemes", "s", "z"],
                "R": ["viseme_r", "visemer", "r"],
                "L": ["viseme_l", "visemel", "l"],
                "WQ": ["viseme_wq", "visemewq", "w", "q"],
                "REST": ["viseme_rest", "visemerest", "rest", "sil", "neutral"]
              };
              for (const [v, aliases] of Object.entries(map)) {
                if (aliases.some(a => lk === a || lk.includes(a))) {
                  this.visemeTargets.set(v, { mesh: o, idx: o.morphTargetDictionary[k] });
                }
              }
            }

          }
        });

        this.onProgress(1);
      },
      (xhr) => {
        if (xhr.total) this.onProgress(xhr.loaded / xhr.total);
      },
      (err) => {
        console.error(err);
        this.onProgress(1);
      }
    );
  }

  attachAudioElement(audioEl) {
    this.audioEl = audioEl;
    if (!this.audioEl) return;
    // init analyser on first play
    const ensure = () => {
      if (this.audioCtx) return;
      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const src = this.audioCtx.createMediaElementSource(this.audioEl);
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 256;
      const bufferLength = this.analyser.frequencyBinCount;
      this.dataArray = new Uint8Array(bufferLength);
      src.connect(this.analyser);
      this.analyser.connect(this.audioCtx.destination);
    };
    this.audioEl.addEventListener("play", ensure);
  }

  _findFirstAction(names) {
    const actionKeys = Object.keys(this.actions);
    for (const n of names) {
      // Exact match
      if (this.actions[n]) return n;
      // Fuzzy match
      for (const key of actionKeys) {
        if (key.includes(n)) return key;
      }
    }
    return null;
  }

  play(name) {
    const actionKeys = Object.keys(this.actions);
    if (!name || actionKeys.length === 0) return;

    const key = name.toLowerCase();
    let action = this.actions[key];

    // Fuzzy search if no exact match
    if (!action) {
      for (const k of actionKeys) {
        if (k.includes(key)) {
          action = this.actions[k];
          break;
        }
      }
    }
    if (!action) return;

    if (this.currentAction && this.currentAction !== action) {
      this.currentAction.fadeOut(0.18);
    }
    action.reset().fadeIn(0.18).play();
    this.currentAction = action;
  }

  setVisemeTimeline(timeline) {
    this.visemeTimeline = timeline;
    this.visemeIndex = 0;
  }

  _applyViseme(viseme, intensity = 1.0) {
    if (!this.visemeTargets.size) return;
    for (const t of this.visemeTargets.values()) {
      if (t.mesh && t.mesh.morphTargetInfluences) t.mesh.morphTargetInfluences[t.idx] = 0;
    }
    const t = this.visemeTargets.get((viseme || "REST").toUpperCase()) || this.visemeTargets.get("REST");
    if (t && t.mesh && t.mesh.morphTargetInfluences) {
      t.mesh.morphTargetInfluences[t.idx] = Math.max(0, Math.min(1, intensity));
    }
  }

  updateVisemes() {
    if (!this.audioEl || !this.visemeTimeline || !this.visemeTimeline.length) return;
    const t = this.audioEl.currentTime || 0;
    while (this.visemeIndex < this.visemeTimeline.length - 1 && t > this.visemeTimeline[this.visemeIndex].t1) {
      this.visemeIndex++;
    }
    const cur = this.visemeTimeline[this.visemeIndex];
    if (!cur) return;
    if (t >= cur.t0 && t <= cur.t1) this._applyViseme(cur.viseme, 0.95);
    else this._applyViseme("REST", 0.2);
  }

  // Backend sends: animation (idle/speak/happy/empathetic) + emotion (calm/happy/empathetic)
  // This method handles the 'animation' field from backend response
  setState(state, emotion = null) {
    if (!this.params) {
      this.params = { state: 'idle', emotion: 'calm', isSpeaking: false, isListening: false };
    }

    this.params.state = state;
    if (emotion) {
      this.params.emotion = emotion;
    }

    // Map backend animation states to available model animations
    // Extended with realistic emotion states
    const animationMap = {
      idle: ["idle", "blink", "breath", "default"],
      speak: ["speak", "talk", "speaking", "idle"],
      happy: ["smile", "happy", "joy", "idle"],
      laughing: ["laugh", "smile", "happy", "idle"],
      empathetic: ["sad", "empathetic", "concern", "idle"],
      crying: ["cry", "sad", "tear", "empathetic", "idle"],
      surprised: ["surprise", "shock", "amazed", "idle"],
      angry: ["angry", "mad", "frown", "idle"],
      thinking: ["think", "ponder", "idle"],
      listening: ["listen", "idle"],
      processing: ["thinking", "idle"]
    };

    // Apply realistic morph targets for emotions
    this._applyEmotionMorphs(state, emotion);

    // Auto-focus when speaking or showing emotion
    if (state === 'speak' || state === 'happy' || state === 'empathetic' ||
      state === 'laughing' || state === 'crying' || state === 'surprised' || state === 'angry') {
      this.setFocus(true);
      this.params.isSpeaking = (state === 'speak');
      this.params.isListening = false;
      this.lastActivityTime = Date.now();
    } else if (state === 'listening') {
      // User is providing input - stop hologram movement, look at camera
      this.setFocus(true);
      this.params.isListening = true;
      this.params.isSpeaking = false;
      this.lastActivityTime = Date.now();
    } else if (state === 'idle') {
      // Delay going back to idle look-around
      this.params.isSpeaking = false;
      this.params.isListening = false;
      setTimeout(() => this.setFocus(false), 2000);
    } else if (state === 'processing' || state === 'thinking') {
      // Keep focus during processing
      this.setFocus(true);
      this.params.isListening = false;
      this.lastActivityTime = Date.now();
    }

    // Find and play the appropriate animation
    const candidates = animationMap[state] || animationMap.idle;
    const animName = this._findFirstAction(candidates);
    if (animName) {
      this.play(animName);
    }
  }

  // Apply realistic morph blends for different emotions
  _applyEmotionMorphs(state, emotion) {
    if (!this.mesh || !this.mesh.morphTargetDictionary) return;

    const dict = this.mesh.morphTargetDictionary;
    const morphs = this.mesh.morphTargetInfluences;

    // Smoothing factor for natural transitions
    const blend = 0.15;

    // Define emotion morph configurations (realistic expressions)
    const emotionMorphs = {
      happy: {
        'browInnerUp': 0.2,
        'cheekSquintLeft': 0.4, 'cheekSquintRight': 0.4,
        'mouthSmileLeft': 0.6, 'mouthSmileRight': 0.6,
        'eyeSquintLeft': 0.2, 'eyeSquintRight': 0.2
      },
      laughing: {
        'browInnerUp': 0.3,
        'cheekSquintLeft': 0.7, 'cheekSquintRight': 0.7,
        'mouthSmileLeft': 0.9, 'mouthSmileRight': 0.9,
        'mouthOpen': 0.4, 'jawOpen': 0.3,
        'eyeSquintLeft': 0.5, 'eyeSquintRight': 0.5
      },
      crying: {
        'browInnerUp': 0.6,
        'browOuterUpLeft': -0.3, 'browOuterUpRight': -0.3,
        'eyeSquintLeft': 0.4, 'eyeSquintRight': 0.4,
        'mouthFrownLeft': 0.5, 'mouthFrownRight': 0.5,
        'mouthPucker': 0.2, 'jawOpen': 0.1
      },
      surprised: {
        'browInnerUp': 0.8, 'browOuterUpLeft': 0.6, 'browOuterUpRight': 0.6,
        'eyeWideLeft': 0.7, 'eyeWideRight': 0.7,
        'jawOpen': 0.4, 'mouthOpen': 0.3
      },
      angry: {
        'browDownLeft': 0.7, 'browDownRight': 0.7,
        'noseSneerLeft': 0.4, 'noseSneerRight': 0.4,
        'jawForward': 0.3,
        'mouthFrownLeft': 0.3, 'mouthFrownRight': 0.3
      },
      thinking: {
        'browInnerUp': 0.3,
        'eyeLookUpLeft': 0.4, 'eyeLookUpRight': 0.4,
        'mouthPucker': 0.15
      },
      empathetic: {
        'browInnerUp': 0.4,
        'mouthFrownLeft': 0.2, 'mouthFrownRight': 0.2,
        'eyeSquintLeft': 0.15, 'eyeSquintRight': 0.15
      },
      idle: {} // Reset to neutral
    };

    const targetMorphs = emotionMorphs[state] || emotionMorphs[emotion] || emotionMorphs.idle;

    // Collect all possible emotion morph keys
    const emotionKeys = new Set();
    Object.values(emotionMorphs).forEach(e => Object.keys(e).forEach(k => emotionKeys.add(k)));

    // Smoothly blend toward target values
    for (const key of emotionKeys) {
      if (dict[key] !== undefined) {
        const idx = dict[key];
        const target = targetMorphs[key] || 0;
        morphs[idx] = morphs[idx] + (target - morphs[idx]) * blend;
      }
    }
  }

  // New method: Called when user starts typing or recording
  setListening(isListening) {
    if (isListening) {
      this.setState('listening');
    } else {
      // Check inactivity timer before returning to idle
      if (Date.now() - this.lastActivityTime > this.idleTimeout) {
        this.setState('idle');
      }
    }
  }

  // New method: Check inactivity and return to idle if needed
  // Returns true if timeout was triggered (so caller can announce message)
  checkInactivityTimeout() {
    if (this.params && this.params.state !== 'idle' && this.params.state !== 'speak') {
      if (Date.now() - this.lastActivityTime > this.idleTimeout) {
        console.log('Inactivity timeout - returning to idle');
        // Don't call setState here - let the caller handle the announcement
        return true;
      }
    }
    return false;
  }

  // Convenience method to set both animation and emotion from backend response
  setStateFromBackend(response) {
    // response = { animation: 'speak', emotion: 'happy', lipsync: {...} }
    const animation = response.animation || 'idle';
    const emotion = response.emotion || 'calm';

    this.setState(animation, emotion);

    if (response.lipsync && response.lipsync.visemes) {
      this.setVisemeTimeline(response.lipsync.visemes);
    }
  }

  setFocus(focused) {
    this.isFocused = focused;
  }

  updateProcedural(dt) {
    // dt is in SECONDS (e.g., 0.016 for 60fps)
    // Scale phase increments appropriately for smooth animation
    // Keep breathing and blinking phases running always (not blocked by listening)
    this.breathPhase += dt * 2.5;    // Natural breathing rhythm (~0.4Hz)

    // Only update idle/look phases when NOT listening (rotation is blocked)
    if (!this.params || !this.params.isListening) {
      this.idlePhase += dt * 0.8;      // Gentle idle sway
      this.lookPhase += dt * 0.3;      // Slow idle look-around
    }

    if (this.modelRoot) {
      // Breathing vertical movement - ALWAYS active (subtle bob)
      this.modelRoot.position.y = -0.2 + Math.sin(this.breathPhase) * 0.008;

      // Default light intensities
      if (!this.baseLightIntensity) {
        this.baseLightIntensity = 1.5;
      }
      const lights = this.scene.children.filter(l => l.isDirectionalLight);
      const keyLight = lights[0];
      const rimLight = lights[2];

      // LISTENING STATE - Freeze rotation ONLY, face camera directly
      // Keep all other animations (blinking, lip-sync, breathing) running
      if (this.params && this.params.isListening) {
        // Snap to face camera and FREEZE rotation
        const dx = this.camera.position.x - this.modelRoot.position.x;
        const dz = this.camera.position.z - this.modelRoot.position.z;
        const angleToCam = Math.atan2(dx, dz);

        // Quick lerp to face camera, then stay frozen
        const currentRot = this.modelRoot.rotation.y;
        const diff = angleToCam - currentRot;
        if (Math.abs(diff) > 0.01) {
          // Still turning to face user
          this.modelRoot.rotation.y = THREE.MathUtils.lerp(currentRot, angleToCam, dt * 10.0);
        }
        // Once facing user, rotation stays frozen (no further updates)

        // Keep head level (no tilt) when listening
        this.modelRoot.rotation.z = THREE.MathUtils.lerp(this.modelRoot.rotation.z, 0, dt * 5.0);

      } else {
        // NORMAL MODE - rotation animations active
        let targetRotY = this.modelRoot.rotation.y;

        if (this.isFocused) {
          // FOCUS / SPEAK - look at camera
          const dx = this.camera.position.x - this.modelRoot.position.x;
          const dz = this.camera.position.z - this.modelRoot.position.z;
          const angleToCam = Math.atan2(dx, dz);
          targetRotY = angleToCam;

          // Reset head tilt when focused
          this.modelRoot.rotation.z = THREE.MathUtils.lerp(
            this.modelRoot.rotation.z,
            0,
            dt * 3.0
          );
        } else {
          // IDLE - gentle sway looking around
          targetRotY = Math.sin(this.lookPhase) * 0.25 + Math.sin(this.lookPhase * 0.7) * 0.1;
        }

        // PROCESSING STATE - Pulsing Light effect
        if (this.params && this.params.state === 'processing') {
          const pulse = Math.sin(Date.now() * 0.006) * 0.5 + 0.5;
          if (keyLight) keyLight.intensity = this.baseLightIntensity + (pulse * 1.5);
          // Subtle oscillation during processing
          targetRotY += Math.sin(Date.now() * 0.003) * 0.15;
        } else {
          // Smoothly restore light
          if (keyLight) {
            keyLight.intensity = THREE.MathUtils.lerp(
              keyLight.intensity,
              this.baseLightIntensity,
              dt * 4.0
            );
          }
        }

        // Smooth rotation lerp (responsive but not jerky)
        const diff = targetRotY - this.modelRoot.rotation.y;
        this.modelRoot.rotation.y += diff * dt * 5.0;
      }

      // EMOTION-based visual effects - ALWAYS active
      if (this.params && this.params.emotion) {
        const emotion = this.params.emotion;
        const lerpSpeed = dt * 3.0;

        if (emotion === 'happy' && rimLight) {
          rimLight.color.lerp(new THREE.Color(0xffdd88), lerpSpeed);
          rimLight.intensity = THREE.MathUtils.lerp(rimLight.intensity, 2.5, lerpSpeed);
        } else if (emotion === 'empathetic' && rimLight) {
          rimLight.color.lerp(new THREE.Color(0x6699ff), lerpSpeed);
          rimLight.intensity = THREE.MathUtils.lerp(rimLight.intensity, 1.8, lerpSpeed);
        } else if (rimLight) {
          rimLight.color.lerp(new THREE.Color(0x00ffff), lerpSpeed);
          rimLight.intensity = THREE.MathUtils.lerp(rimLight.intensity, 2.0, lerpSpeed);
        }
      }

      // Speaking state - slightly more active breathing
      if (this.params && this.params.isSpeaking) {
        this.modelRoot.position.y = -0.2 + Math.sin(this.breathPhase * 1.8) * 0.012;
      }
    }

    this.blinkTimer += dt;
    if (this.blinkTimer > this.nextBlink) {
      this._doBlink();
      this.blinkTimer = 0;
      this.nextBlink = 2 + Math.random() * 4;
    }

    // Natural eye movement - saccades and smooth tracking
    this._updateEyeMovement(dt);
  }

  _updateEyeMovement(dt) {
    // Timer for next random eye movement
    this.eyeMoveTimer += dt;

    if (this.eyeMoveTimer > this.nextEyeMove) {
      // Generate new random look target (small movements, human-like)
      if (this.isFocused || (this.params && this.params.isListening)) {
        // When focused/listening, look mostly at user with tiny variations
        this.eyeLookTarget.set(
          (Math.random() - 0.5) * 0.1,
          (Math.random() - 0.5) * 0.08
        );
      } else {
        // Idle - larger, more exploratory movements
        this.eyeLookTarget.set(
          (Math.random() - 0.5) * 0.4,
          (Math.random() - 0.5) * 0.25
        );
      }
      this.eyeMoveTimer = 0;
      this.nextEyeMove = 0.5 + Math.random() * 2.5; // Next movement in 0.5-3s
    }

    // Smooth interpolation to target (saccade-like quick movement then settle)
    const lerpSpeed = 8.0; // Fast but smooth
    this.eyeLookCurrent.x += (this.eyeLookTarget.x - this.eyeLookCurrent.x) * dt * lerpSpeed;
    this.eyeLookCurrent.y += (this.eyeLookTarget.y - this.eyeLookCurrent.y) * dt * lerpSpeed;

    // Apply to eye bones
    for (const eyeBone of this.eyeBones) {
      if (eyeBone) {
        // Y rotation for left-right look, X for up-down
        eyeBone.rotation.y = this.eyeLookCurrent.x;
        // Don't override X if we're blinking
        if (!this._isBlinking) {
          eyeBone.rotation.x = this.eyeLookCurrent.y;
        }
      }
    }
  }

  _doBlink() {
    const bones = this.eyeBones || [];
    if (!bones.length) return;
    this._isBlinking = true;
    for (const b of bones) b.rotation.x += 0.35;
    setTimeout(() => {
      for (const b of bones) b.rotation.x -= 0.35;
      this._isBlinking = false;
    }, 90);
  }

  updateLipSync() {
    // Speaking - animate mouth based on audio
    if (!this.analyser || !this.dataArray || !this.audioEl) {
      // No audio setup - do nothing (don't reset morphs constantly)
      return;
    }

    // Check if we're actually supposed to be speaking
    const shouldSpeak = this.params && this.params.isSpeaking &&
      !this.audioEl.paused && !this.audioEl.ended;

    if (shouldSpeak) {
      // Mark that we're actively speaking
      this._wasSpeeking = true;

      this.analyser.getByteFrequencyData(this.dataArray);

      // Calculate audio intensity with threshold
      let sum = 0;
      for (let i = 0; i < this.dataArray.length; i++) sum += this.dataArray[i];
      const rawIntensity = sum / 15000;

      // Apply threshold - mouth doesn't move for very quiet/silent parts
      const threshold = 0.05;
      const intensity = rawIntensity > threshold ?
        Math.min(1, (rawIntensity - threshold) / (1 - threshold)) : 0;

      // Smooth the intensity for more natural movement
      if (!this._lastMouthIntensity) this._lastMouthIntensity = 0;
      const smoothing = 0.3; // Lower = smoother
      this._lastMouthIntensity += (intensity - this._lastMouthIntensity) * smoothing;
      const smoothIntensity = this._lastMouthIntensity;

      if (this.jawBone) {
        this.jawBone.rotation.x = -smoothIntensity * 0.22;
      }
      for (const mt of this.morphTargets) {
        mt.mesh.morphTargetInfluences[mt.idx] = smoothIntensity * 0.85;
      }
    } else if (this._wasSpeeking) {
      // Just stopped speaking - smoothly close mouth
      this._wasSpeeking = false;
      this._lastMouthIntensity = 0;

      if (this.jawBone) {
        this.jawBone.rotation.x = 0;
      }
      for (const mt of this.morphTargets) {
        mt.mesh.morphTargetInfluences[mt.idx] = 0;
      }
      this._applyViseme("REST", 0.1);
    }
    // If not speaking and wasn't speaking, do nothing (preserve other animations)
  }

  // New method: Force reset mouth animation (called when speech ends)
  resetMouth() {
    this._wasSpeeking = false; // Prevent updateLipSync from resetting again
    if (this.jawBone) {
      this.jawBone.rotation.x = 0;
    }
    for (const mt of this.morphTargets) {
      mt.mesh.morphTargetInfluences[mt.idx] = 0;
    }
    this._applyViseme("REST", 0.1);
  }

  // Sync Monitor: Continuously monitor hologram for desynchronization
  // Checks mouth, nose, face elements and auto-corrects drift
  syncMonitor() {
    if (!this.mesh) return;

    // Check morph targets exist and are in valid range
    const morphTargets = this.mesh.morphTargetInfluences;
    if (!morphTargets) return;

    let needsReset = false;

    // Check for NaN or out-of-range values
    for (let i = 0; i < morphTargets.length; i++) {
      if (isNaN(morphTargets[i]) || morphTargets[i] < -0.1 || morphTargets[i] > 1.5) {
        console.warn('🔧 Sync issue detected in morph target', i, morphTargets[i]);
        morphTargets[i] = 0;
        needsReset = true;
      }
    }

    // If not speaking, ensure mouth morphs are near zero
    if (!this.analyser && !this.isSpeaking) {
      const mouthMorphs = ['jawOpen', 'mouthOpen', 'viseme_aa', 'viseme_O', 'viseme_E'];
      const dict = this.mesh.morphTargetDictionary;
      if (dict) {
        for (const name of mouthMorphs) {
          if (dict[name] !== undefined) {
            const idx = dict[name];
            if (morphTargets[idx] > 0.15) {
              // Smoothly return to closed
              morphTargets[idx] *= 0.85;
            }
          }
        }
      }
    }

    // Monitor rotation drift
    if (this.hologramGroup) {
      const rot = this.hologramGroup.rotation;
      // Clamp excessive rotations
      if (Math.abs(rot.x) > 0.5) rot.x = Math.sign(rot.x) * 0.5;
      if (Math.abs(rot.z) > 0.3) rot.z = Math.sign(rot.z) * 0.3;
    }

    if (needsReset) {
      console.log('🔧 Hologram sync auto-corrected');
    }
  }

  resize() {
    if (!this.container || !this.camera || !this.renderer) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
    if (this.composer) {
      this.composer.setSize(w, h);
      const pixelRatio = this.renderer.getPixelRatio();
      // Update FXAA
      for (const pass of this.composer.passes) {
        if (pass.material && pass.material.uniforms['resolution']) {
          pass.material.uniforms['resolution'].value.x = 1 / (w * pixelRatio);
          pass.material.uniforms['resolution'].value.y = 1 / (h * pixelRatio);
        }
      }
    }
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    const delta = this.clock.getDelta();
    this.controls.update();
    if (this.mixer) this.mixer.update(delta);

    this.updateProcedural(delta); // delta is already in seconds, no multiplication!
    this.updateVisemes();
    this.updateLipSync();
    this.syncMonitor(); // Monitor for desync issues

    // Render directly - simpler and more reliable
    this.renderer.render(this.scene, this.camera);
  }
}
