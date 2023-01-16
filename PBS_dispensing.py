from opentrons import protocol_api
from constants.PBS_constants import *
from opentrons_tools.distribute_tools import distribute_vol_and_offsets, reorder_distribute_dict

import math
# metadata
metadata = {
    'protocolName': 'PBS_dispensing',
    'author': 'Microbiologia HU La Paz',
    'source': 'Custom Protocol Request',
    'apiLevel': '2.3',
    'author' : 'Iván Bloise-Sánchez'
}
VERSION = '1.0.0'

#192 es el máximod e tubos que se pueden llenar con 8 racks de 24
NUMBER_OF_TUBES = 192

#Variables del programa
DISP_VOLUME_UL = 500
DISP_VOLUME_ML = DISP_VOLUME_UL / 1000
MAX_EPPENDORF_RACK_ADMIT = 8
MAX_FALCON_RACK_ADMIT = 1
FALCON_VOLUME_ML = 50
PBS_LOST_PERCENT = 0.025 #Calculo en tanto por 1 del excedente de PBS necesario por perdidas de adherencia, etc
OFFSET_ITERATES = [80, 50, 20, 5]
P1000_FLOW_ASPIRATE = 600
P100_FLOW_DISPENSE = 1000
P1000_FLOW_BLOWOUT = 1000
START_WELL = 0

# Dict labwares-> habría que pasarlo a clases

EPPENDORF_LABWARE = {
    LABWARE_NAME : 'opentrons_24_tuberack_eppendorf_2ml_safelock_snapcap',
    LABWARE_SLOTS : ['10', '7', '4', '1', '11', '8', '5', '2'],
    LABWARE_LABEL : "Opentrons Rack de tubos eppendorf de 2 mL",
    LABWARE_TYPE : TUBERACK_TYPE,
    TUBE_COUNT : 24
}
FALCON_LABWARE = {
    LABWARE_NAME : 'opentrons_6_tuberack_falcon_50ml_conical',
    LABWARE_SLOTS : ['6'],
    LABWARE_LABEL : 'Opentrons Rack de tubos falcon 50 mL' ,
    LABWARE_TYPE : TUBERACK_TYPE,
    TUBE_COUNT : 6
}

P1000_PIPETTE = {
    PIPETTE_LABWARE_NAME_KEY :'p1000_single_gen2',
    PIPETTE_POSITION_KEY : RIGHT_POSITION,
    PIPETTE_LABEL_KEY : 'Opentrons P1000 single gen2',
    TIP_RACK_LABWARE_NAME_KEY : 'opentrons_96_filtertiprack_1000ul',
    TIP_RACK_SLOT_LIST_KEY : ['3'],
    TIP_RACK_LABEL_KEY : '1000µl tiprack'
}

#Calculo de variables
EPPENDORF_RACKS_NEEDED = math.ceil(NUMBER_OF_TUBES/EPPENDORF_LABWARE[TUBE_COUNT])
VOLUME_ML_PBS_NEEDED = DISP_VOLUME_ML * NUMBER_OF_TUBES
FALCON_TUBES_NEEDED = math.ceil((VOLUME_ML_PBS_NEEDED + VOLUME_ML_PBS_NEEDED * PBS_LOST_PERCENT)/FALCON_VOLUME_ML)
FALCON_RACKS_NEEDED = math.ceil(FALCON_TUBES_NEEDED/FALCON_LABWARE[TUBE_COUNT])
EPPEDORF_FILL_FOR_FALCON = math.floor(FALCON_VOLUME_ML / (DISP_VOLUME_ML + DISP_VOLUME_ML * PBS_LOST_PERCENT))
RACKS_FILL_FOR_FALCON = math.floor(EPPEDORF_FILL_FOR_FALCON / EPPENDORF_LABWARE[TUBE_COUNT]) # Vamos a RACKS completos
EPPENDORFS_FILL_BY_OFFSET_ITERATE = math.floor(RACKS_FILL_FOR_FALCON * EPPENDORF_LABWARE[TUBE_COUNT] / len(OFFSET_ITERATES))
RACKS_FILL_BY_ITERATE = math.floor(EPPENDORFS_FILL_BY_OFFSET_ITERATE/EPPENDORF_LABWARE[TUBE_COUNT])
EPPENDORFS_IN_LAST_ITER = RACKS_FILL_FOR_FALCON * EPPENDORF_LABWARE[TUBE_COUNT] - EPPENDORFS_FILL_BY_OFFSET_ITERATE * (len(OFFSET_ITERATES)- 1)

#Calculamos la iteración de pipeteo
distribute_dict = distribute_vol_and_offsets(NUMBER_OF_TUBES, EPPENDORF_LABWARE[LABWARE_SLOTS], FALCON_LABWARE[LABWARE_SLOTS],
OFFSET_ITERATES,EPPENDORF_LABWARE[TUBE_COUNT],FALCON_LABWARE[TUBE_COUNT], EPPENDORFS_FILL_BY_OFFSET_ITERATE, tube_rack_slot_key=DEST_LBW_SLOT_KEY,
tube_well_key=DEST_LBW_WELL_KEY, falcon_tube_rack_slot_key=SRC_LBW_SLOT_KEY, falcon_well_key=SRC_LBW_WELL_KEY, offset_key=OFFSET_KEY)

def run(ctx: protocol_api.ProtocolContext):
    if EPPENDORF_RACKS_NEEDED > MAX_EPPENDORF_RACK_ADMIT or FALCON_RACKS_NEEDED > MAX_FALCON_RACK_ADMIT: 
        ctx.comment('El número de eppendorf o de tubos falcon excede el permitido')
        exit()
    else:
        EPPENDORF_LABWARE[LABWARE_SLOTS] = [EPPENDORF_LABWARE[LABWARE_SLOTS][idx] for idx in range(EPPENDORF_RACKS_NEEDED)]
    # load labware
    source_rack = {str(slot) : ctx.load_labware(
        FALCON_LABWARE[LABWARE_NAME], slot,
        FALCON_LABWARE[LABWARE_LABEL] + SLOT_LABEL_SUFFIX + str(slot)) 
        for slot in FALCON_LABWARE[LABWARE_SLOTS]
    }
    
    eppendorf_racks = {str(slot) : ctx.load_labware(
        EPPENDORF_LABWARE[LABWARE_NAME], slot,
        EPPENDORF_LABWARE[LABWARE_LABEL] + SLOT_LABEL_SUFFIX + str(slot))
        for slot in EPPENDORF_LABWARE[LABWARE_SLOTS]
    }

    tipracks1000 = [
        ctx.load_labware(
            P1000_PIPETTE[TIP_RACK_LABWARE_NAME_KEY],slot, P1000_PIPETTE[TIP_RACK_LABEL_KEY] + f'_slot {str(index)}') 
            for index, slot in enumerate(P1000_PIPETTE[TIP_RACK_SLOT_LIST_KEY])]

    # load pipette
    p1000 = ctx.load_instrument(
        P1000_PIPETTE[PIPETTE_LABWARE_NAME_KEY], P1000_PIPETTE[PIPETTE_POSITION_KEY], tip_racks=tipracks1000)

    #Rates
    p1000.flow_rate.aspirate = P1000_FLOW_ASPIRATE
    p1000.flow_rate.dispense = P100_FLOW_DISPENSE
    p1000.flow_rate.blow_out = P1000_FLOW_BLOWOUT
    
    #get orders
    orders = reorder_distribute_dict(distribute_dict, eppendorf_racks, falcon_rack_slot=SRC_LBW_SLOT_KEY, falcon_well= SRC_LBW_WELL_KEY,
    offset=OFFSET_KEY, rack_slot_key= DEST_LBW_SLOT_KEY, tube_well_key=DEST_LBW_WELL_KEY, distribute_well_key=DISTRIBUTE_WELL_KEY)

    #distribute
    p1000.pick_up_tip()
    for order in orders.values():
        source = source_rack[order[SRC_LBW_SLOT_KEY]].wells()[order[SRC_LBW_WELL_KEY]]
        p1000.distribute(
            volume = DISP_VOLUME_UL,
            source = source.bottom(order[OFFSET_KEY]),
            dest=order[DISTRIBUTE_WELL_KEY],
            disposal_volume=0,
            new_tip = 'never'
        )
    p1000.drop_tip()