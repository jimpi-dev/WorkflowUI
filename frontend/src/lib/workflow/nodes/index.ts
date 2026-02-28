import { KSamplerSpec } from './KSampler';
import { CLIPTextEncodeSpec } from './CLIPTextEncode';
import { PowerLoraLoaderSpec } from './PowerLoraLoader';
import { SaveImageSpec } from './SaveImage';
import { PrimitiveStringMultilineSpec } from './PrimitiveStringMultiline';
import { EmptySD3LatentImageSpec } from './EmptySD3LatentImage';
import { EmptyLatentImageSpec } from './EmptyLatentImage';
import { SDXLEmptyLatentSizePickerSpec } from './SDXLEmptyLatentSizePicker';
import { LoadImageSpec } from './LoadImage';
import { CheckpointLoaderSimpleSpec } from './CheckpointLoaderSimple';
import { ImageScaleBySpec } from './ImageScaleBy';
import { VHS_VideoCombineSpec } from './VHS_VideoCombine';
import { VAEDecodeSpec } from './VAEDecode';
import { IntSpec } from './Int';
import { FloatSpec } from './Float';
import { EasyIntSpec } from './EasyInt';
import { EasySeedSpec } from './EasySeed';
import { KSamplerAdvancedSpec } from './KSamplerAdvanced';
import { LoraLoaderModelOnlySpec } from './LoraLoaderModelOnly';
import { TextEncodeAceStepAudio1_5Spec } from './TextEncodeAceStepAudio1_5';
import { EmptyAceStep1_5LatentAudioSpec } from './EmptyAceStep1_5LatentAudio';
import { SaveAudioMP3Spec } from './SaveAudioMP3';
import { AudioQualityEnhancerSpec } from './AudioQualityEnhancer';
import { KSamplerSelectSpec } from './KSamplerSelect';
import { RandomNoiseSpec } from './RandomNoise';
import { UNETLoaderSpec } from './UNETLoader';
import { CLIPLoaderSpec } from './CLIPLoader';
import { VAELoaderSpec } from './VAELoader';
import { EmptyFlux2LatentImageSpec } from './EmptyFlux2LatentImage';
import { ImageScaleToTotalPixelsSpec } from './ImageScaleToTotalPixels';
import { Flux2SchedulerSpec } from './Flux2Scheduler';
import {
    SamplerCustomAdvancedSpec,
    CFGGuiderSpec,
    ConditioningZeroOutSpec,
    GetImageSizeSpec,
    ReferenceLatentSpec,
    VAEEncodeSpec,
    ImageUpscaleWithModelSpec,
    AnySwitchRgthreeSpec,
    T5TokenizerOptionsSpec
} from './flux2InternalNodes';
import { ModelSamplingAuraFlowSpec } from './ModelSamplingAuraFlow';
import { ImageScaleSpec } from './ImageScale';
import { VAEEncodeTiledSpec } from './VAEEncodeTiled';
import { UpscaleModelLoaderSpec } from './UpscaleModelLoader';
import { VAEDecodeTiledSpec } from './VAEDecodeTiled';
import { LatentUpscaleBySpec } from './LatentUpscaleBy';
import { SeedRgthreeSpec } from './SeedRgthree';
import { CRLatentInputSwitchSpec } from './CRLatentInputSwitch';
import { BasicSchedulerSpec } from './BasicScheduler';

export const NODE_SPECS = {
    KSampler: KSamplerSpec,
    CLIPTextEncode: CLIPTextEncodeSpec,
    'Power Lora Loader (rgthree)': PowerLoraLoaderSpec,
    SaveImage: SaveImageSpec,
    PrimitiveStringMultiline: PrimitiveStringMultilineSpec,
    EmptySD3LatentImage: EmptySD3LatentImageSpec,
    EmptyLatentImage: EmptyLatentImageSpec,
    'SDXLEmptyLatentSizePicker+': SDXLEmptyLatentSizePickerSpec,
    LoadImage: LoadImageSpec,
    CheckpointLoaderSimple: CheckpointLoaderSimpleSpec,
    ImageScaleBy: ImageScaleBySpec,
    VHS_VideoCombine: VHS_VideoCombineSpec,
    VAEDecode: VAEDecodeSpec,
    Int: IntSpec,
    Float: FloatSpec,
    'easy int': EasyIntSpec,
    'easy seed': EasySeedSpec,
    KSamplerAdvanced: KSamplerAdvancedSpec,
    LoraLoaderModelOnly: LoraLoaderModelOnlySpec,
    KSamplerSelect: KSamplerSelectSpec,
    RandomNoise: RandomNoiseSpec,
    UNETLoader: UNETLoaderSpec,
    CLIPLoader: CLIPLoaderSpec,
    VAELoader: VAELoaderSpec,
    EmptyFlux2LatentImage: EmptyFlux2LatentImageSpec,
    ImageScaleToTotalPixels: ImageScaleToTotalPixelsSpec,
    Flux2Scheduler: Flux2SchedulerSpec,
    BasicScheduler: BasicSchedulerSpec,
    SamplerCustomAdvanced: SamplerCustomAdvancedSpec,
    CFGGuider: CFGGuiderSpec,
    ConditioningZeroOut: ConditioningZeroOutSpec,
    GetImageSize: GetImageSizeSpec,
    ReferenceLatent: ReferenceLatentSpec,
    VAEEncode: VAEEncodeSpec,
    ImageUpscaleWithModel: ImageUpscaleWithModelSpec,
    'Any Switch (rgthree)': AnySwitchRgthreeSpec,
    T5TokenizerOptions: T5TokenizerOptionsSpec,
    ModelSamplingAuraFlow: ModelSamplingAuraFlowSpec,
    ImageScale: ImageScaleSpec,
    VAEEncodeTiled: VAEEncodeTiledSpec,
    UpscaleModelLoader: UpscaleModelLoaderSpec,
    VAEDecodeTiled: VAEDecodeTiledSpec,
    LatentUpscaleBy: LatentUpscaleBySpec,
    'Seed (rgthree)': SeedRgthreeSpec,
    'CR Latent Input Switch': CRLatentInputSwitchSpec,
    'TextEncodeAceStepAudio1.5': TextEncodeAceStepAudio1_5Spec,
    'EmptyAceStep1.5LatentAudio': EmptyAceStep1_5LatentAudioSpec,
    SaveAudioMP3: SaveAudioMP3Spec,
    AudioQualityEnhancer: AudioQualityEnhancerSpec
};