'''

Code for calculating keys parallely on n-1 CPU cores, where n = Total CPU cores on the system.

@authors: Venkata Sarika Kondra
'''
import os,math,ntpath,socket,argparse
from os.path import expanduser
from pathlib import Path
import glob, re
import time
import pandas as pd
from itertools import combinations
from collections import Counter
from joblib import Parallel, delayed, cpu_count


parser = argparse.ArgumentParser(description='Parallel Key Generation.')
parser.add_argument('--sample_name', '-sample', metavar='sample_name', default='t2', \
    help='Name of the sample on which this script should be run.')
parser.add_argument('--path', '-path', metavar='path', \
    default=os.path.join(expanduser('~'),"Dropbox\\PC\\Downloads\\TSR\\data\\"), \
    help='Directory of input sample and other files.')
parser.add_argument('--thetaBounds', '-theta', metavar='thetaBounds', \
    default = '0,12.11,17.32,21.53,25.21,28.54,31.64,34.55,37.34,40.03,42.64,45.17,47.64,50.05,52.43,54.77,57.08,59.38,61.64,63.87,66.09,68.30,70.5,72.69,79.2,81.36,83.51,85.67,87.8,90', \
    #default='0 , 14.1, 20.31,25.49, 29.99, 34.1, 38, 41.7,45.3, 48.61, 51.91, 55.19, 58.29, 61.3, 64.39, 67.3, 70.3, 73.11, 81.69, 84.49, 87.29, 90 ', \
    help='Bin Boundaries for Theta.')
parser.add_argument('--distBounds', '-dist', metavar='distBounds', \
    default = '3.83, 7.00, 9.00, 11.00, 14.00, 17.99, 21.25, 23.19, 24.8, 26.26,27.72, 28.9, 30.36, 31.62, 32.76, 33.84, 35.13, 36.26,37.62,38.73, 40.12,41.8, 43.41, 45.55, 47.46, 49.69, 52.65, 55.81, 60.2, 64.63, 70.04, 76.15,83.26, 132.45', \
    #default='2.81, 7.00, 9.00, 11.00, 14.00, 17.4, 24.16, 30.19, 36.37, 44.78, 175.52', \
    help='Bin Boundaries for maxDist.')
parser.add_argument('--size_gap', '-size_gap', metavar='size_gap', \
    default = 10000, \
    help='Max Distance greater than this will be eliminated')
parser.add_argument('--skip', '-skip', metavar='skip', default=False, \
    help='To get only amino acids count make this True')
parser.add_argument('--is_chain', '-is_chain', action='store_true', \
    default=True, help='Pass this argument if there is chain information in the sample_details file.')
parser.add_argument('--needDistribution', '-needDistribution', \
    action='store_true', default=False, \
    help='Enable this option if theta and distance distribution plots are required.')
parser.add_argument('--needTriplets', '-needTriplets', \
    action='store_true', default=False, \
    help='Enable this option if triplet files are required.')
parser.add_argument('--is_seq', '-is_seq', \
    action='store_true', default=True, \
    help='Enable this option if amino acid sequence numbers are there in details file.')

#Changed according to Sarika's binning
def thetaClass_( binBoundaries, value, type):
        classL = -1
        for i in binBoundaries:
            if value < binBoundaries[0]:#Bins are seperately handled for theta and maxdist.
                if type == 0: #Thetas are not allowed to be less than zero.
                    print(value,binBoundaries[0], 'out of index',binBoundaries )       
                else:
                    classL = binBoundaries.index(binBoundaries[0])+1
                break
            if (value < i) :#If the value is less than the boundary it falls in previous bin.
                if type ==0: classL = binBoundaries.index(i) 
                else: classL =binBoundaries.index(i) + 1
                break
        if value >= binBoundaries[-1]:
            if type ==0:
                if value == binBoundaries[-1]: classL = binBoundaries.index(binBoundaries[-1])
            else : classL = binBoundaries.index(binBoundaries[-1]) +2
        return classL

def calcDist(indexLabel1,indexLabel2):
        x1=xCord[indexLabel1]
        x2=xCord[indexLabel2]
        y1=yCord[indexLabel1]
        y2=yCord[indexLabel2]
        z1=zCord[indexLabel1]
        z2=zCord[indexLabel2]
        distance=(((x1-x2)**2+(y2-y1)**2+(z2-z1)**2)**0.5)
        return distance

def indexFind(index_of_2,i1,j1,k1):
        if index_of_2==i1:
            indexOf0=j1
            indexOf1=k1
        elif index_of_2==j1:
            indexOf0=i1
            indexOf1=k1
        elif index_of_2==k1:
            indexOf0=i1
            indexOf1=j1

        return indexOf0, indexOf1

def processFiles(filePath, args, outFolder, dTheta, dLen, aa_seq, aminoAcidLabel, thetaBounds, distBounds, numOfLabels,protein_chain):
        fileName = ntpath.basename(filePath).split('.')[0].upper()
        print( fileName)
        start_time=time.time()
        if args.is_chain and (fileName not in protein_chain.keys()):
            print("{} not in sample_details file.".format(fileName))
            error_string = "not in sample_details"
            if args.needDistribution:
                return (fileName + '({})'.format(error_string), 0, 0, 0, 0, 0, [], None, None)
            else:
                return (fileName + '({})'.format(error_string), 0, 0, 0, 0, 0, [])
        if os.path.exists(os.path.join(outFolder, "{}.keys_theta{}_dist{}".\
            format(fileName, str(dTheta), str(dLen)))):
            print("{} already exists".format(fileName))
            error_string = "already exists"
            if args.needDistribution:
                return (fileName+ '({})'.format(error_string), 0, 0, 0, 0, 0, [], None, None)
            else:
                return (fileName + '({})'.format(error_string), 0, 0, 0, 0, 0, [])
        #Read the chain name from details file if is_chain argument is passed
        if args.is_chain:
            chainName = None
            print( fileName, ':', chainName)

        filesDict={}
        thetaDict = {}
        lengthDict = {}
        inFile=open(filePath,'r')
        outFile2 = open(os.path.join(outFolder, "{}.keys_theta{}_dist{}".\
            format(fileName, str(dTheta), str(dLen))), "w") 

        if args.needTriplets:       
            fileTriplets = open(os.path.join(outFolder,"{}.triplets_theta{}_dist{}".  \
                format(fileName, str(dTheta), str(dLen))), "w")

        allDistances = []

        global xCord, yCord, zCord
        aminoAcidName={}
        xCord={}
        yCord={}
        zCord={}
        seq_number={}
        counter=0
        aminoacidCount = []
        c = 0
        unknown_aas = set()
        combs_counter = []
        for i in inFile:
            if (len(i) < 20):
                continue
            aa = i[17:20]
            chain_in_file = i[21]
            if (i[0:6].rstrip()=="NUMMDL"):
                numOfModels=i[10:14].rstrip()
            if (i[0:6].rstrip()=="MODEL" and int(i[10:14].rstrip())>1):
                break
            if args.is_chain:                 
                if(i[0:4].rstrip())=="ATOM" and (i[13:15].rstrip())=="CA" \
                    and (i[16]=='A'or i[16]==' ') and aa != "UNK" \
                    and (chain_in_file in protein_chain[fileName]): 
                    #print(f"{chain_in_file}_{i[22:27].rstrip()}_{counter}", fileName)
                    if (aa_seq is not None) and (fileName in aa_seq) and (chain_in_file in aa_seq[fileName])\
                        and (int(re.findall(r'[0-9]+',i[22:27].strip())[0]) \
                            not in aa_seq[fileName][chain_in_file])  :
                        continue
                    aminoacidCount.append(aa)
                    aminoAcidName[f"{chain_in_file}_{counter}"]=int(aminoAcidLabel[aa])
                    xCord[f"{chain_in_file}_{counter}"]=(float(i[30:38]))
                    yCord[f"{chain_in_file}_{counter}"]=(float(i[38:46]))
                    zCord[f"{chain_in_file}_{counter}"]=(float(i[46:54]))
                    seq_number[f"{chain_in_file}_{counter}"]= chain_in_file+"_"+str(re.findall(r'[0-9]+',i[22:27].strip())[0])
                    combs_counter.append(f"{chain_in_file}_{counter}")
                    counter += 1
                    chainName = chain_in_file
            
        protLen=len(yCord)
        #print(combs_counter)
        lst_combs = list(combinations(combs_counter,3))
        req_combs = []
        for comb in lst_combs:
            if comb[0].split("_")[0] == comb[1].split("_")[0] == comb[2].split("_")[0]:
                continue
            else:
                req_combs.append(comb)

        if unknown_aas:
            print('Unknown amino acids found. Skipped {} protein.{}'.format(fileName, list(unknown_aas)))
            if args.needDistribution:
                return (fileName, 0, 0, 0, 0, 0, ";".join(list(unknown_aas)),{}, {})                            
            else:
                return (fileName, protLen, 0, 0, 0, 0, ";".join(list(unknown_aas)))
                            
        if (not args.skip) and (protLen != 0):
            outFile2 = open(os.path.join(outFolder, "{}.keys_theta{}_dist{}".\
            format(fileName, str(dTheta), str(dLen))), "w") 
            if args.needTriplets:       
                fileTriplets = open(os.path.join(outFolder,"{}.triplets_theta{}_dist{}".  \
                    format(fileName, str(dTheta), str(dLen))), "w")

            
            initialLabel=[]
            sortedLabel=[]
            sortedIndex=[]
            outDist={}
            for m in range(0,3):
                initialLabel.append(0)
                sortedLabel.append(0)
                sortedIndex.append(0)
            
            for i,j,k in req_combs:
                        global i1,j1,k1
                        #print(i,j,k)
                        i1 = i #= i.split("_")[-1]
                        j1 = j #= j.split("_")[-1]
                        k1 = k #= k.split("_")[-1]
                        keepLabelIndex={}
                        keepLabelIndex[aminoAcidName[i]] = i
                        keepLabelIndex[aminoAcidName[j]] = j
                        keepLabelIndex[aminoAcidName[k]] = k
                        initialLabel[0] = aminoAcidName[i]
                        initialLabel[1] = aminoAcidName[j]
                        initialLabel[2] = aminoAcidName[k]
                        sortedLabel = list(initialLabel)
                        sortedLabel.sort(reverse=True)
                        if (sortedLabel[0] == sortedLabel[1]) and \
                            (sortedLabel[1] == sortedLabel[2]):
                            dist1_2Temp = calcDist(i,j)
                            dist1_3Temp = calcDist(i,k)
                            dist2_3Temp = calcDist(j,k)
                            if dist1_2Temp>=(max(dist1_2Temp,dist1_3Temp,dist2_3Temp)):
                                indexOf0 = i
                                indexOf1 = j
                                indexOf2 = k
                            elif dist1_3Temp>=(max(dist1_2Temp,dist1_3Temp,dist2_3Temp)):
                                indexOf0 = i
                                indexOf1 = k
                                indexOf2 = j
                            else:
                                indexOf0 = j
                                indexOf1 = k
                                indexOf2 = i
                        elif(aminoAcidName[i] != aminoAcidName[j]) and \
                            (aminoAcidName[i] != aminoAcidName[k]) and \
                            (aminoAcidName[j] != aminoAcidName[k]):
                            for index_ in range(0,3):
                                sortedIndex[index_] = keepLabelIndex[sortedLabel[index_]]
                            indexOf0 = sortedIndex[0]
                            indexOf1 = sortedIndex[1]
                            indexOf2 = sortedIndex[2]

                        elif(sortedLabel[0] == sortedLabel[1]) and \
                            (sortedLabel[1] != sortedLabel[2]):
                            indexOf2 = keepLabelIndex[sortedLabel[2]]
                            indices = indexFind(indexOf2,i,j,k)
                            a = indexOf2
                            b = indices[0]
                            c = indices[1]
                            dist1_3Temp = calcDist(b,a)
                            dist2_3Temp = calcDist(c,a)
                            if dist1_3Temp >= dist2_3Temp:
                                indexOf0 = indices[0]
                                indexOf1 = indices[1] 
                            else:
                                indexOf0 = indices[1]
                                indexOf1 = indices[0]

                        elif(sortedLabel[0] != sortedLabel[1]) and (sortedLabel[1] == sortedLabel[2]):
                            indexOf0 = keepLabelIndex[sortedLabel[0]]
                            indices =indexFind(indexOf0,i,j,k)
                            if calcDist(indexOf0,indices[0])>= calcDist(indexOf0,indices[1]):
                                indexOf1=indices[0]
                                indexOf2=indices[1] 
                            else:
                                indexOf2=indices[0]
                                indexOf1=indices[1]
                        dist01=calcDist(indexOf0,indexOf1)
                        s2=dist01/2
                        dist02=calcDist(indexOf0,indexOf2)
                        s1=dist02
                        dist12=dist01
                        dist03=calcDist(indexOf1,indexOf2)
                        maxDist=max(dist01,dist02,dist03)
                        allDistances.append(maxDist)
                        if maxDist < int(args.size_gap):

                            s3 = (((xCord[indexOf0] + xCord[indexOf1])/2 - xCord[indexOf2])**2 + \
                                ((yCord[indexOf0] + yCord[indexOf1])/2 - yCord[indexOf2])**2 + \
                                ((zCord[indexOf0] + zCord[indexOf1])/2 - zCord[indexOf2])**2)**0.5
                            Theta1 = 180*(math.acos((s1**2-s2**2-s3**2)/(2*s2*s3)))/3.14
                            if Theta1 <= 90:
                                Theta = Theta1
                            else:
                                Theta=abs(180-Theta1)
                            if args.needDistribution:
                                try:
                                    thetaDict[round(Theta,0)] += 1
                                except:
                                    thetaDict[round(Theta,0)] = 1

                                try:
                                    lengthDict[round(maxDist,1)] += 1
                                except:
                                    lengthDict[round(maxDist,1)] = 1

                            classT1=thetaClass_(thetaBounds,Theta,0)
                            classL1=thetaClass_(distBounds, maxDist,1)

                            ##getting the positions of AminoAcids in sequence
                            position0 = seq_number[indexOf0] #str(list(seq_number.values())[indexOf0])
                            position1 = seq_number[indexOf1] #str(list(seq_number.values())[indexOf1])
                            position2 = seq_number[indexOf2] #str(list(seq_number.values())[indexOf2])

                            aacd0 = list(aminoAcidLabel.keys())[list(aminoAcidLabel.values()).index(aminoAcidName[indexOf0])]
                            aacd1 = list(aminoAcidLabel.keys())[list(aminoAcidLabel.values()).index(aminoAcidName[indexOf1])]
                            aacd2 =list(aminoAcidLabel.keys())[list(aminoAcidLabel.values()).index(aminoAcidName[indexOf2])]
                            #print(aminoAcidLabel.keys())

                            x0 = str(xCord.get(indexOf0))
                            y0 = str(yCord.get(indexOf0))
                            z0 = str(zCord.get(indexOf0))

                            x1 = str(xCord.get(indexOf1))
                            y1 = str(yCord.get(indexOf1))
                            z1 = str(zCord.get(indexOf1))

                            x2 = str(xCord.get(indexOf2))
                            y2 = str(yCord.get(indexOf2))
                            z2 = str(zCord.get(indexOf2))


                            key_2 = dLen*dTheta*(numOfLabels**2)*(aminoAcidName[indexOf0]-1) + \
                                    dLen*dTheta*(numOfLabels)*(aminoAcidName[indexOf1]-1) + \
                                    dLen*dTheta*(aminoAcidName[indexOf2]-1) + dTheta*(classL1-1) + (classT1-1)    

                            # if maxDist >53.1004999882:
                            #     c = c+1                   
                            if key_2 in filesDict:
                                filesDict[key_2] += 1
                            else:
                                filesDict[key_2] = 1

                            if args.needTriplets:  
                                line = (str(key_2) +"\t" + str(aacd0) + "\t" + str(position0) + "\t" + \
                                    str(aacd1) + "\t" + str(position1) + "\t" + str(aacd2) + "\t" + \
                                    str(position2) + "\t" + str(classT1) + "\t" + str(Theta) + "\t" +\
                                    str(classL1) + "\t" + str(maxDist) + "\t" + x0 + "\t" + y0 + "\t" + \
                                    z0 + "\t" + x1 + "\t" + y1 + "\t" + z1 + "\t" + x2 + "\t" + y2 + "\t" + z2 + "\n")
                                fileTriplets.writelines(line)

            for value_ in filesDict:
                outFile2.writelines([str(value_),'\t', str(filesDict[value_]),'\n'])
            outFile2.close()
            if args.needTriplets:
                fileTriplets.close()
        end_time=time.time()
        total_time=((end_time)-(start_time))
        print("FILENAME=",fileName,"NUM OF AMINOACIDS=",protLen)
        print("{} took : {} mins.".format(fileName, total_time/60))
        if args.needDistribution:
            return (fileName, \
                    protLen, \
                    len(filesDict), \
                    sum(list(filesDict.values())), \
                    max(allDistances) if len(allDistances) > 0 else 0, \
                    min(allDistances) if len(allDistances) > 0 else 0, \
                    list(unknown_aas),
                    thetaDict, \
                    lengthDict )
        else:
            return (fileName, \
                    protLen, \
                    len(filesDict), \
                    sum(list(filesDict.values())), \
                    max(allDistances) if len(allDistances) > 0 else 0, \
                    min(allDistances) if len(allDistances) > 0 else 0,
                    list(unknown_aas))

if __name__ == '__main__':
    """Executable code starts here."""
    start_time = time.time()
    args = parser.parse_args()
    thetaBounds = list(map(float, args.thetaBounds.split(',')))
    dTheta = len(thetaBounds) - 1
    distBounds = list(map(float, args.distBounds.split(',')))
    dLen = len(distBounds) + 1
    numOfLabels = 20

    print("Working on theta: [{}], dist: [{}] \nSize Gap: [{}] \nPrinting Distribution Files?: [{}] \nUsing Chain Information?: [{}]"\
        .format(str(dTheta), str(dLen), str(args.size_gap), str(args.needDistribution), str(args.is_chain)))

    aminoAcidCode=open(os.path.join(args.path, "aminoAcidCode_map.txt"),"r") 
    aminoAcidLabel={}
    for amino in aminoAcidCode:
        amino = amino.split()
        aminoAcidLabel[amino[0]] = int(amino[1])
    aminoAcidCode.close()

    df = pd.read_csv(os.path.join(args.path, args.sample_name, "sample_details.csv"))
    print(df)
    df.rename(columns={'PDB ID':'protein', 'Chain ID': 'chain'}, inplace=True)
    df['protein'] = df['protein'].str.upper()
    protein_chain={}
    if args.is_chain: 
        for index, protein_row in df.iterrows(): 
            protein_chain[protein_row["protein"] ]= [protein_row["chain_1"], protein_row["chain_2"]]
            print(protein_chain)

    aa_seq = None
    if args.is_seq:
        if (not 'chain_1_aa' in df.columns) or (not 'chain_2_aa' in df.columns):
            print("aa columns are not present for selection of a range of aa from protein.")
            exit()
        else:
            aa_seq = {}
            for index,protein_row in df.iterrows():
                req_aa_chain = {}    
                for chain_no,chain_aa in enumerate([protein_row["chain_1_aa"], protein_row["chain_2_aa"]]):     
                    req_aa = []  
                    if chain_aa != "Unknown":             
                        for pairs in chain_aa.split(";"):
                            if len(pairs.rsplit('-', 1))>1:
                                req_aa += range(int(pairs.rsplit('-', 1)[0]), int(pairs.rsplit('-', 1)[1]) + 1)
                            elif len(pairs.rsplit('-', 1)) == 1:
                                req_aa += [int(pairs.rsplit('-', 1)[0])]
                        req_aa_chain[protein_chain[protein_row["protein"]][chain_no]] = req_aa
                if len(req_aa_chain) > 0:
                    aa_seq[protein_row["protein"]] = req_aa_chain
            print(aa_seq)

    outFolder = os.path.join(args.path, args.sample_name, "theta{}_dist{}".format(str(dTheta), str(dLen)))
    #Create output directory
    if not os.path.exists(outFolder):
        os.makedirs(outFolder)   

    fileType = "*.pdb"  #"*.ent"#  
    files=glob.glob(os.path.join(args.path, args.sample_name, fileType)) 
    # result = [
    #     processFiles(fileName, args, outFolder, dTheta, dLen, aa_seq, aminoAcidLabel, thetaBounds, distBounds, numOfLabels, protein_chain) for fileName in files]
    result = Parallel(n_jobs=cpu_count() - 1, verbose=10, backend="multiprocessing", batch_size="auto")\
                (delayed(processFiles)(fileName, args, outFolder, dTheta, dLen, aa_seq, aminoAcidLabel, thetaBounds, distBounds, numOfLabels, protein_chain) for fileName in files)
    #It gets enabled if you need to see the Theta and Distance Distribution
    if args.needDistribution:
        d_theta = {}
        d_dist = {}
        req_result = []
        for row in result:
            print('row:',row)
            d_theta = Counter(d_theta) + Counter(row[7])
            d_dist = Counter(d_dist) + Counter(row[8])
            req_result.append((row[0], row[1], row[2], row[3], row[4], row[5], []))
        pd.DataFrame(d_theta.items(),columns = ['theta','freq']).sort_values('theta').to_csv('{}//theta_distribution.csv'.\
            format(outFolder))
        pd.DataFrame(d_dist.items(),columns = ['length','freq']).sort_values('length').to_csv('{}//length_distribution.csv'.\
            format(outFolder))
        result = req_result
    
    df2 = pd.DataFrame(result,columns = ['protein','aa_count','#keys', '#keys with freq', 'max_distance', 'min_distance', 'unknown_aas'])
    df2.to_csv(os.path.join(args.path, args.sample_name, 'sample_details2.csv'))
    print(" {} proteins are exempted from Key Calculation: ".format(len(df2[df2['#keys'] == 0])))

    print("Parallel Key Generation completed in {} mins.".format((time.time() - start_time)/60))
    