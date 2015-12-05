#!/usr/bin/python

import os
import numpy as np
import matplotlib.pyplot as plt
import ConfigParser
import json
import re
from scipy import misc

def generate_MS_tk(ms_command):
    # Simulate T2 values using MS.
    # The input is a string containing the MS-command
    # The output is a list of float containing independent values of Tk
    # where Tk is the first coalescent event of the sample
    o = os.popen(ms_command).read()
    newick_re = "\([(0-9.,:)]+\)" # Find the tree line
    newick_pattern = re.compile(newick_re)
    single_coal_re = "\([0-9.,:]+\)"
    single_coal_pattern = re.compile(single_coal_re)
    t_obs = []
    for newick_line in newick_pattern.finditer(o):
        newick_text = newick_line.group()
        coal_times = []
        for single_coal_event in single_coal_pattern.finditer(newick_text):
            matched_text = single_coal_event.group()
            coal_time = float(matched_text.split(':')[1].split(',')[0])
            coal_times.append(coal_time)
        t_obs.append(min(coal_times))
    return t_obs

def generate_MS_t2(ms_command):
    # Simulate T2 values using MS.
    # The input is a string containing the MS-command
    # The output is a list of float containing independent values of T2
    o = os.popen(ms_command).read()
    o = o.split('\n')
    t_obs = []
    for l in o:
        if l[:6] == 'time:\t':
            temp = l.split('\t')
            t_obs.append(float(temp[1]))
    return t_obs

def compute_real_history_from_ms_command(ms_command, N0):
    # Returns a function depending on the scenario found in the ms_command
    # First we compute the value of N0
    msc = ms_command.split(' ')

    # Case of instantaneous changes
    if ms_command.__contains__('-eN'):
        size_changes = ms_command.split(' -eN ')
        (t_k, alpha_k) = ([i.split(' ')[0] for i in size_changes[1:]], 
                             [j.split(' ')[1] for j in size_changes[1:]])
        t_k = [0]+[4*N0*float(t) for t in t_k]
        N_k = [N0]+[N0*float(alpha) for alpha in alpha_k]
        return ('-eN', t_k, N_k)
        # print 'case 1'
    # Case of exponential grow
    elif ms_command.__contains__('G'):
        alpha = float(msc[msc.index('-G') + 1])
        T = float(msc[msc.index('-G') + 3])
        return ('ExponGrow', [alpha, T, N0])
        # print 'exponnential grow'
    # StSI case
    elif ms_command.__contains__('-I'):
        n = int(msc[msc.index('-I') + 1])
        M = float(msc[msc.index('-I') + n+2])
        if msc[msc.index('-I') + 2] == '2':
            return ('StSI same_island', [n, M, N0])
        else:
            return ('StSI disctint_island', [n, M, N0])
    else:
        return ('-eN', [[0], [N0]])

def compute_empirical_dist(obs, x_vector='', dx=0):
    # This method computes the empirical distribution given the
    # observations.
    # The functions are evaluated in the x_vector parameter
    # by default x_vector is computed as a function of the data
    # by default the differences 'dx' are a vector 

    if x_vector == '':
        actual_x_vector = np.arange(0, max(obs)+0.1, 0.1)

    elif x_vector[-1]<=max(obs):
        actual_x_vector = list(x_vector)
        actual_x_vector.append(max(obs))
        actual_x_vector = np.array(x_vector)
    else:
        actual_x_vector = np.array(x_vector)
        
    if (dx == 0):
        dx = actual_x_vector[1:]-actual_x_vector[:-1]
        # Computes the cumulative distribution and the distribution
        x_vector_left = actual_x_vector[1:] - np.true_divide(dx,2)
        x_vector_right = actual_x_vector[1:] + np.true_divide(dx,2)
        x_vector_left = np.array([0,0] + list(x_vector_left))
        x_vector_right = np.array([0, actual_x_vector[0]+dx[0]] + list(x_vector_right))
        actual_dx = np.array([dx[0]]+list(dx))
    else:
        actual_dx = dx
        half_dx = np.true_divide(dx,2)
    
    counts, ignored_values = np.histogram(obs, bins = actual_x_vector)
    counts_left, ignored_values = np.histogram(obs, bins = x_vector_left)
    counts_right, ignored_values = np.histogram(obs, bins = x_vector_right)
    
    cdf_x = counts.cumsum()
    cdf_x = np.array([0]+list(cdf_x))
    cdf_left = counts_left.cumsum()
    cdf_right = counts_right.cumsum()
    
    """
    # Normalizing
    cdf_obs_x = np.true_divide(cdf_x,len(obs))
    cdf_left = np.true_divide(cdf_left, len(obs))
    cdf_right = np.true_divide(cdf_right, len(obs))
    """

    # now we compute the pdf (the derivative of the cdf)
    dy = cdf_right - cdf_left
    pdf_obs_x = np.true_divide(dy, actual_dx)

    return (cdf_x, pdf_obs_x)

def compute_t_vector(start, end, number_of_values, vector_type):
    if vector_type == 'linear':
        x_vector = np.linspace(start, end, number_of_values)
    elif vector_type == 'log':
        n = number_of_values
        x_vector = [0.1*(np.exp(i * np.log(1+10*end)/n)-1)
                    for i in range(n+1)]
        x_vector[0] = x_vector[0]+start
    else:
        # For the moment, the default output is a linspace distribution
        x_vector = np.linspace(start, end, number_of_values)
    return np.array(x_vector)

def group_t(time_interval, pattern):
    # Groupes the time following the pattern as specifyed in the psmc
    # documentation
    constant_blocks = pattern.split('+')
    t = list(time_interval)
    t = t[:]+t[-1:]
    temp = [t[0]]
    current_pos = 0
    for b in constant_blocks:
        if b.__contains__('*'):
            n_of_blocks = int(b.split('*')[0])
            size_of_blocks = int(b.split('*')[1])
            for i in xrange(n_of_blocks):
                temp.append(t[current_pos+size_of_blocks])
                current_pos+=size_of_blocks
        else:
            size_of_blocks = int(b)
            temp.append(t[current_pos+size_of_blocks])
            current_pos+=size_of_blocks
    return np.array(temp)

def compute_IICR_n_islands(n, M, t, s=1):
    # This method evaluates the lambda function in a vector
    # of time values t.
    # If 's' is True we are in the case when two individuals where
    # sampled from the same island. If 's' is false, then the two
    # individuals where sampled from different islands.

    # Computing constants
    gamma = np.true_divide(M, n-1)
    delta = (1+n*gamma)**2 - 4*gamma
    alpha = 0.5*(1+n*gamma + np.sqrt(delta))
    beta =  0.5*(1+n*gamma - np.sqrt(delta))
    c = np.true_divide(gamma, beta-alpha)

    # Now we evaluate
    x_vector = t
    if s:
        numerator = (1-beta)*np.exp(-alpha*x_vector) + (alpha-1)*np.exp(-beta*x_vector)
        denominator = (alpha-gamma)*np.exp(-alpha*x_vector) + (gamma-beta)*np.exp(-beta*x_vector)
    else:
        numerator = beta*np.exp(-alpha*(x_vector)) - alpha*np.exp(-beta*(x_vector))
        denominator = gamma * (np.exp(-alpha*(x_vector)) - np.exp(-beta*(x_vector)))

    lambda_t = np.true_divide(numerator, denominator)

    return lambda_t


class ParamsLoader():
    # We use it for loading the parameters from a file
    def __init__(self, path2params='./parameters.txt'):
        self.path2params = path2params
        [self.path2ms, self.ms_command, self.dx, self.original_time_interval, 
         self.pattern, self.N0, self.g_time, self.plot_real, 
         self.plot_limits, self.n_rep] = self.load_parameters()
        self.times_vector = self.group_t(self.original_time_interval, 
                                          self.pattern)

    def group_t(self, time_interval, pattern):
        # Groupes the time following the pattern as specifyed in the psmc
        # documentation
        constant_blocks = pattern.split('+')
        t = list(time_interval)
        t = t[:]+t[-1:]
        temp = [t[0]]
        current_pos = 0
        for b in constant_blocks:
            if b.__contains__('*'):
                n_of_blocks = int(b.split('*')[0])
                size_of_blocks = int(b.split('*')[1])
                for i in xrange(n_of_blocks):
                    temp.append(t[current_pos+size_of_blocks])
                    current_pos+=size_of_blocks
            else:
                size_of_blocks = int(b)
                temp.append(t[current_pos+size_of_blocks])
                current_pos+=size_of_blocks
        return np.array(temp)
    
    def load_parameters(self):
        parser = ConfigParser.ConfigParser()
        parser.read(self.path2params)
        
        path2ms = parser.get('ms_parameters', 'path2ms')
        ms_command = parser.get('ms_parameters', 'ms_command')
        dx = float(parser.get('computation_parameters', 'dx'))
        if parser.get('custom_x_vector', 'set_custom_xvector') == 'False':
            start = float(parser.get('computation_parameters', 'start'))
            end = float(parser.get('computation_parameters', 'end'))
            number_of_values = int(parser.get('computation_parameters', 
                                              'number_of_values'))
            vector_type = parser.get('computation_parameters', 'x_vector_type')
            if vector_type == 'linear':
                x_vector = np.linspace(start, end, number_of_values)
            elif vector_type == 'log':
                n = number_of_values
                x_vector = [0.1*(np.exp(i * np.log(1+10*end)/n)-1)
                            for i in range(n+1)]
                x_vector[0] = x_vector[0]+start
            else:
                # For the moment, the default output is a linspace distribution
                x_vector = np.linspace(start, end, number_of_values)
        x_vector = np.array(x_vector)
        pattern = parser.get('computation_parameters', 'pattern')
        N0 = float(parser.get('scale_params', 'N0'))
        g_time = int(parser.get('scale_params', 'generation_time'))
        plot_real = int(parser.get('plot_params', 'plot_real_ms_history'))==1
        limits = parser.get('plot_params', 'plot_limits')
        plot_limits = [float(i) for i in limits.split(',')]
        n_rep = int(parser.get('number_of_repetitions', 'n_rep'))
        return [path2ms, ms_command, dx, x_vector, pattern, N0, g_time, 
                plot_real, plot_limits, n_rep]

if __name__ == "__main__":
    with open('parameters.json') as json_params:
        p = json.load(json_params)
    
    if p["custom_x_vector"]["set_custom_xvector"] == 0:
            start = p["computation_parameters"]["start"]
            end = p["computation_parameters"]["end"]
            number_of_values = p["computation_parameters"]["number_of_values"]
            vector_type = p["computation_parameters"]["x_vector_type"]
            t_vector = compute_t_vector(start, end, number_of_values, vector_type)
    
    pattern = p["computation_parameters"]["pattern"]
    empirical_histories = []
    times_vector = group_t(t_vector, pattern)
    dx = p["computation_parameters"]["dx"]
    # Do n independent simulations     
    for i in range(len(p["scenarios"])):
        ms_full_cmd = os.path.join(p["path2ms"], p["scenarios"][i]["ms_command"])
        obs = generate_MS_tk(ms_full_cmd)
        obs = 2*np.array(obs) # Given that in ms time is scaled to 4N0 and 
        # our model scales times to 2N0, we multiply the output of MS by 2.
        (F_x, f_x) = compute_empirical_dist(obs, times_vector, dx)
        F_x = np.array(F_x)
        x = times_vector
        # If the sample size on the ms command is greater than 2
        # the IICR that we obtain when the sample size is 2
        # must be multiplied by a factor
        
        # Parsing the ms command for getting the sample size
        ms_command = p["scenarios"][i]["ms_command"]
        sample_size = int(ms_command.split("ms ")[1].split(" ")[0])
        factor = misc.comb(sample_size, 2)
        
        empirical_lambda = factor * np.true_divide(len(obs)-F_x, f_x)
        empirical_histories.append((x, empirical_lambda))
    # empirical_lambda = np.true_divide((1-F_x[:-1])*(x[1:]-x[:-1]), 
    #                                  F_x[1:]-F_x[:-1])

    # Do the plot    
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)
    
    N0 = p["scale_params"]["N0"]
    g_time = p["scale_params"]["generation_time"]
    for i in range(len(empirical_histories)):
        (x, empirical_lambda) = empirical_histories[i]
        x[0] = float(x[1])/5 # this is for avoiding to have x[0]=0 in a logscale
        linecolor = p["scenarios"][i]["color"]
        line_style = p["scenarios"][i]["linestyle"]
        alpha = p["scenarios"][i]["alpha"]
        plot_label = p["scenarios"][i]["label"]
        ax.step(2 * N0 * g_time*x, N0 * empirical_lambda, color = linecolor,
                ls=line_style, where='post', alpha=alpha, label=plot_label)
    
    # Plot the real history (if commanded)
    if p["plot_params"]["plot_real_ms_history"]:
        [case, x, y] = compute_real_history_from_ms_command(p.ms_command, p.N0)
        print(case)
        print(x)
        print(y)
        x[0] = min(float(x[1])/5, p.plot_limits[2]) # this is for avoiding 
        # to have x[0]=0 in a logscale
        x.append(1e7) # adding the last value 
        y.append(y[-1])
        ax.step(x, y, '-b', where='post', label='Real history')
        
    if p["plot_params"]["plot_theor_IICR"]:
        theoretical_IICR_list = []
        T_max = np.log10(p["plot_params"]["plot_limits"][1])
        t_k = np.logspace(1, T_max, 1000)
        t_k = np.true_divide(t_k, 2 * N0 * g_time)
        for i in range(len(p["theoretical_IICR_nisland"])):
            n = p["theoretical_IICR_nisland"][i]["n"]
            M = p["theoretical_IICR_nisland"][i]["M"]
            theoretical_IICR_list.append(compute_IICR_n_islands(n, M, t_k, 1))
            
    # Plotting the theoretical IICR
    for i in range(len(p["theoretical_IICR_nisland"])):
        linecolor = p["theoretical_IICR_nisland"][i]["color"]
        line_style = p["theoretical_IICR_nisland"][i]["linestyle"]
        alpha = p["theoretical_IICR_nisland"][i]["alpha"]        
        plot_label = p["theoretical_IICR_nisland"][i]["label"]
        ax.plot(2 * N0 * g_time * t_k, N0 * theoretical_IICR_list[i],
                color=linecolor, ls=line_style, alpha=alpha, label=plot_label)
    
    ax.set_xlabel('Time (in years)')
    ax.set_ylabel(r'Instantaneous Coalescence rates $\lambda(t)$')
    ax.set_xscale('log')
    
    plt.legend(loc='best')
    [x_a, x_b, y_a, y_b] = p["plot_params"]["plot_limits"]
    plt.xlim(x_a, x_b)
    plt.ylim(y_a, y_b)
    plt.show()
    
    #fig.savefig('./plot.png', dpi=300)