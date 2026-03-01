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
import { CheckpointLoaderSpec } from './CheckpointLoader';
import { DiffusionModelLoaderSpec } from './DiffusionModelLoader';
import { LoadDiffusionModelSpec } from './LoadDiffusionModel';
import { StableCascadeCheckpointLoaderSpec } from './StableCascadeCheckpointLoader';
import { SD3CheckpointLoaderSpec } from './SD3CheckpointLoader';
import { FluxCheckpointLoaderSpec } from './FluxCheckpointLoader';
import { ImageScaleBySpec } from './ImageScaleBy';
import { VHS_VideoCombineSpec } from './VHS_VideoCombine';
import { VAEDecodeSpec } from './VAEDecode';
import { IntSpec } from './Int';
import { FloatSpec } from './Float';
import { EasyIntSpec } from './EasyInt';
import { EasySeedSpec } from './EasySeed';
import { KSamplerAdvancedSpec } from './KSamplerAdvanced';
import { LoraLoaderSpec } from './LoraLoader';
import { LoraLoaderModelOnlySpec } from './LoraLoaderModelOnly';
import { LycorisLoaderSpec } from './LycorisLoader';
import { TextEncodeAceStepAudio1_5Spec } from './TextEncodeAceStepAudio1_5';
import { EmptyAceStep1_5LatentAudioSpec } from './EmptyAceStep1_5LatentAudio';
import { SaveAudioMP3Spec } from './SaveAudioMP3';
import { AudioQualityEnhancerSpec } from './AudioQualityEnhancer';
import { KSamplerSelectSpec } from './KSamplerSelect';
import { RandomNoiseSpec } from './RandomNoise';
import { UNETLoaderSpec } from './UNETLoader';
import { CLIPLoaderSpec } from './CLIPLoader';
import { DualCLIPLoaderSpec } from './DualCLIPLoader';
import { TripleCLIPLoaderSpec } from './TripleCLIPLoader';
import { CLIPVisionLoaderSpec } from './CLIPVisionLoader';
import { T5LoaderSpec } from './T5Loader';
import { TextEncoderLoaderSpec } from './TextEncoderLoader';
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
import { ESRGANLoaderSpec } from './ESRGANLoader';
import { RealESRGANLoaderSpec } from './RealESRGANLoader';
import { SwinIRLoaderSpec } from './SwinIRLoader';
import { VAEDecodeTiledSpec } from './VAEDecodeTiled';
import { LatentUpscaleBySpec } from './LatentUpscaleBy';
import { SeedRgthreeSpec } from './SeedRgthree';
import { CRLatentInputSwitchSpec } from './CRLatentInputSwitch';
import { BasicSchedulerSpec } from './BasicScheduler';
import { ModelSamplingSD3Spec } from './ModelSamplingSD3';
import { INTConstantSpec } from './INTConstant';
import { UnetLoaderGGUFSpec } from './UnetLoaderGGUF';
import { RifeVfiSpec } from './RifeVfi';
import { ImageResizeKJv2Spec } from './ImageResizeKJv2';
import { TextMultilineSpec } from './TextMultiline';

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
    CheckpointLoader: CheckpointLoaderSpec,
    DiffusionModelLoader: DiffusionModelLoaderSpec,
    LoadDiffusionModel: LoadDiffusionModelSpec,
    StableCascadeCheckpointLoader: StableCascadeCheckpointLoaderSpec,
    'StableCascade_CheckpointLoader': StableCascadeCheckpointLoaderSpec,
    SD3CheckpointLoader: SD3CheckpointLoaderSpec,
    SD3LoadCheckpoint: SD3CheckpointLoaderSpec,
    FluxCheckpointLoader: FluxCheckpointLoaderSpec,
    ImageScaleBy: ImageScaleBySpec,
    VHS_VideoCombine: VHS_VideoCombineSpec,
    VAEDecode: VAEDecodeSpec,
    Int: IntSpec,
    Float: FloatSpec,
    'easy int': EasyIntSpec,
    'easy seed': EasySeedSpec,
    KSamplerAdvanced: KSamplerAdvancedSpec,
    LoraLoader: LoraLoaderSpec,
    LoraLoaderModelOnly: LoraLoaderModelOnlySpec,
    LycorisLoaderNode: LycorisLoaderSpec,
    KSamplerSelect: KSamplerSelectSpec,
    RandomNoise: RandomNoiseSpec,
    UNETLoader: UNETLoaderSpec,
    CLIPLoader: CLIPLoaderSpec,
    DualCLIPLoader: DualCLIPLoaderSpec,
    TripleCLIPLoader: TripleCLIPLoaderSpec,
    CLIPVisionLoader: CLIPVisionLoaderSpec,
    T5Loader: T5LoaderSpec,
    TextEncoderLoader: TextEncoderLoaderSpec,
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
    ESRGANLoader: ESRGANLoaderSpec,
    RealESRGANLoader: RealESRGANLoaderSpec,
    SwinIRLoader: SwinIRLoaderSpec,
    VAEDecodeTiled: VAEDecodeTiledSpec,
    LatentUpscaleBy: LatentUpscaleBySpec,
    'Seed (rgthree)': SeedRgthreeSpec,
    'CR Latent Input Switch': CRLatentInputSwitchSpec,
    'TextEncodeAceStepAudio1.5': TextEncodeAceStepAudio1_5Spec,
    'EmptyAceStep1.5LatentAudio': EmptyAceStep1_5LatentAudioSpec,
    SaveAudioMP3: SaveAudioMP3Spec,
    AudioQualityEnhancer: AudioQualityEnhancerSpec,
    ModelSamplingSD3: ModelSamplingSD3Spec,
    INTConstant: INTConstantSpec,
    UnetLoaderGGUF: UnetLoaderGGUFSpec,
    'RIFE VFI': RifeVfiSpec,
    ImageResizeKJv2: ImageResizeKJv2Spec,
    'Text Multiline': TextMultilineSpec
};