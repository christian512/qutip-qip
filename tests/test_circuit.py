import pytest
import os
import shutil
import numpy as np
from pathlib import Path


from qutip_qip.circuit import (QubitCircuit, CircuitSimulator)
from qutip import (tensor, Qobj, ptrace, rand_ket, fock_dm, basis,
                   rand_dm, bell_state, ket2dm, identity, sigmax)
from qutip_qip.qasm import read_qasm
from qutip_qip.operations import (
    Gate, gates, Measurement, gate_sequence_product
)

from qutip_qip.decompose.decompose_single_qubit_gate import _ZYZ_rotation

import qutip as qp


def _op_dist(A, B):
    return (A - B).norm()


def _teleportation_circuit():
    teleportation = QubitCircuit(3, num_cbits=2,
                                 input_states=["q0", "0", "0", "c0", "c1"])

    teleportation.add_gate("SNOT", targets=[1])
    teleportation.add_gate("CNOT", targets=[2], controls=[1])
    teleportation.add_gate("CNOT", targets=[1], controls=[0])
    teleportation.add_gate("SNOT", targets=[0])
    teleportation.add_measurement("M0", targets=[0], classical_store=1)
    teleportation.add_measurement("M1", targets=[1], classical_store=0)
    teleportation.add_gate("X", targets=[2], classical_controls=[0])
    teleportation.add_gate("Z", targets=[2], classical_controls=[1])

    return teleportation


def _teleportation_circuit2():
    teleportation = QubitCircuit(3, num_cbits=2,
                                 input_states=["q0", "0", "0", "c0", "c1"])

    teleportation.add_gate("SNOT", targets=[1])
    teleportation.add_gate("CNOT", targets=[2], controls=[1])
    teleportation.add_gate("CNOT", targets=[1], controls=[0])
    teleportation.add_gate("SNOT", targets=[0])
    teleportation.add_gate("CNOT", targets=[2], controls=[1])
    teleportation.add_gate("CZ", targets=[2], controls=[0])

    return teleportation


def _measurement_circuit():
    qc = QubitCircuit(2, num_cbits=2)

    qc.add_measurement("M0", targets=[0], classical_store=0)
    qc.add_measurement("M1", targets=[1], classical_store=1)

    return qc


def _simulators_sv(qc):

    sim_sv_precompute = CircuitSimulator(qc, mode="state_vector_simulator",
                                         precompute_unitary=True)
    sim_sv = CircuitSimulator(qc, mode="state_vector_simulator")

    return [sim_sv_precompute, sim_sv]


def _simulators_dm(qc):

    sim_dm_precompute = CircuitSimulator(qc, mode="density_matrix_simulator",
                                         precompute_unitary=True)
    sim_dm = CircuitSimulator(qc, mode="density_matrix_simulator")

    return [sim_dm_precompute, sim_dm]


class TestQubitCircuit:
    """
    A test class for the QuTiP functions for Circuit resolution.
    """

    @pytest.mark.parametrize(["gate_from", "gate_to", "targets", "controls"], [
                        pytest.param("SWAP", "CNOT",
                                        [0, 1], None, id="SWAPtoCNOT"),
                        pytest.param("ISWAP", "CNOT",
                                        [0, 1], None, id="ISWAPtoCNOT"),
                        pytest.param("CSIGN", "CNOT",
                                        [1], [0], id="CSIGNtoCNOT"),
                        pytest.param("CNOT", "CSIGN",
                                        [0], [1], id="CNOTtoCSIGN"),
                        pytest.param("CNOT", "SQRTSWAP",
                                        [0], [1], id="CNOTtoSQRTSWAP"),
                        pytest.param("CNOT", "SQRTISWAP",
                                        [0], [1], id="CNOTtoSQRTISWAP"),
                        pytest.param("CNOT", "ISWAP",
                                        [0], [1], id="CNOTtoISWAP")])
    def testresolve(self, gate_from, gate_to, targets, controls):
        qc1 = QubitCircuit(2)
        qc1.add_gate(gate_from, targets=targets, controls=controls)
        U1 = gate_sequence_product(qc1.propagators())
        qc2 = qc1.resolve_gates(basis=gate_to)
        U2 = gate_sequence_product(qc2.propagators())
        assert _op_dist(U1, U2) < 1e-12

    def testSNOTdecompose(self):
        """
        SNOT to rotation: compare unitary matrix for SNOT and product of
        resolved matrices in terms of rotation gates.
        """
        qc1 = QubitCircuit(1)
        qc1.add_gate("SNOT", targets=0)
        U1 = gate_sequence_product(qc1.propagators())
        qc2 = qc1.resolve_gates()
        U2 = gate_sequence_product(qc2.propagators())
        assert _op_dist(U1, U2) < 1e-12

    def testFREDKINdecompose(self):
        """
        FREDKIN to rotation and CNOT: compare unitary matrix for FREDKIN and product of
        resolved matrices in terms of rotation gates and CNOT.
        """
        qc1 = QubitCircuit(3)
        qc1.add_gate("FREDKIN", targets=[0, 1], controls=[2])
        U1 = gate_sequence_product(qc1.propagators())
        qc2 = qc1.resolve_gates()
        U2 = gate_sequence_product(qc2.propagators())
        assert _op_dist(U1, U2) < 1e-12

    def testadjacentgates(self):
        """
        Adjacent Gates: compare unitary matrix for ISWAP and product of
        resolved matrices in terms of adjacent gates interaction.
        """
        qc1 = QubitCircuit(3)
        qc1.add_gate("ISWAP", targets=[0, 2])
        U1 = gate_sequence_product(qc1.propagators())
        qc0 = qc1.adjacent_gates()
        qc2 = qc0.resolve_gates(basis="ISWAP")
        U2 = gate_sequence_product(qc2.propagators())
        assert _op_dist(U1, U2) < 1e-12

    def test_add_gate(self):
        """
        Addition of a gate object directly to a `QubitCircuit`
        """
        qc = QubitCircuit(6)
        qc.add_gate("CNOT", targets=[1], controls=[0])
        test_gate = Gate("SWAP", targets=[1, 4])
        qc.add_gate(test_gate)
        qc.add_gate("TOFFOLI", controls=[0, 1], targets=[2])
        qc.add_gate("SNOT", targets=[3])
        qc.add_gate(test_gate, index=[3])
        qc.add_1q_gate("RY", start=4, end=5, arg_value=1.570796)

        # Test explicit gate addition
        assert qc.gates[0].name == "CNOT"
        assert qc.gates[0].targets == [1]
        assert qc.gates[0].controls == [0]

        # Test direct gate addition
        assert qc.gates[1].name == test_gate.name
        assert qc.gates[1].targets == test_gate.targets

        # Test specified position gate addition
        assert qc.gates[3].name == test_gate.name
        assert qc.gates[3].targets == test_gate.targets

        # Test adding 1 qubit gate on [start, end] qubits
        assert qc.gates[5].name == "RY"
        assert qc.gates[5].targets == [4]
        assert qc.gates[5].arg_value == 1.570796
        assert qc.gates[6].name == "RY"
        assert qc.gates[6].targets == [5]
        assert qc.gates[5].arg_value == 1.570796

        dummy_gate1 = Gate("DUMMY1")
        inds = [1, 3, 4, 6]
        qc.add_gate(dummy_gate1, index=inds)

        # Test adding gates at multiple (sorted) indices at once.
        # NOTE: Every insertion shifts the indices in the original list of
        #       gates by an additional position to the right.
        expected_gate_names = [
            'CNOT',     # 0
            'DUMMY1',   # 1
            'SWAP',     # 2
            'TOFFOLI',  # 3
            'DUMMY1',   # 4
            'SWAP',     # 5
            'DUMMY1',   # 6
            'SNOT',     # 7
            'RY',       # 8
            'DUMMY1',   # 9
            'RY',       # 10
        ]
        actual_gate_names = [gate.name for gate in qc.gates]
        assert actual_gate_names == expected_gate_names

        dummy_gate2 = Gate("DUMMY2")
        inds = [11, 0]
        qc.add_gate(dummy_gate2, index=inds)

        # Test adding gates at multiple (unsorted) indices at once.
        expected_gate_names = [
            'DUMMY2',   # 0
            'CNOT',     # 1
            'DUMMY1',   # 2
            'SWAP',     # 3
            'TOFFOLI',  # 4
            'DUMMY1',   # 5
            'SWAP',     # 6
            'DUMMY1',   # 7
            'SNOT',     # 8
            'RY',       # 9
            'DUMMY1',   # 10
            'RY',       # 11
            'DUMMY2',   # 12
        ]
        actual_gate_names = [gate.name for gate in qc.gates]
        assert actual_gate_names == expected_gate_names

    def test_add_circuit(self):
        """
        Addition of a circuit to a `QubitCircuit`
        """

        def customer_gate1(arg_values):
            mat = np.zeros((4, 4), dtype=np.complex128)
            mat[0, 0] = mat[1, 1] = 1.
            mat[2:4, 2:4] = gates.rx(arg_values)
            return Qobj(mat, dims=[[2, 2], [2, 2]])

        qc = QubitCircuit(6)
        qc.user_gates = {"CTRLRX": customer_gate1}

        qc = QubitCircuit(6)
        qc.add_gate("CNOT", targets=[1], controls=[0])
        test_gate = Gate("SWAP", targets=[1, 4])
        qc.add_gate(test_gate)
        qc.add_gate("TOFFOLI", controls=[0, 1], targets=[2])
        qc.add_gate("SNOT", targets=[3])
        qc.add_gate(test_gate, index=[3])
        qc.add_measurement("M0", targets=[0], classical_store=[1])
        qc.add_1q_gate("RY", start=4, end=5, arg_value=1.570796)
        qc.add_gate("CTRLRX", targets=[1, 2], arg_value=np.pi/2)

        qc1 = QubitCircuit(6)

        qc1.add_circuit(qc)

        # Test if all gates and measurements are added
        assert len(qc1.gates) == len(qc.gates)

        # Test if the definitions of user gates are added
        assert qc1.user_gates == qc.user_gates

        for i in range(len(qc1.gates)):
            assert (qc1.gates[i].name
                    == qc.gates[i].name)
            assert (qc1.gates[i].targets
                    == qc.gates[i].targets)
            if (isinstance(qc1.gates[i], Gate) and
                    isinstance(qc.gates[i], Gate)):
                assert (qc1.gates[i].controls
                        == qc.gates[i].controls)
                assert (qc1.gates[i].classical_controls
                        == qc.gates[i].classical_controls)
            elif (isinstance(qc1.gates[i], Measurement) and
                    isinstance(qc.gates[i], Measurement)):
                assert (qc1.gates[i].classical_store
                        == qc.gates[i].classical_store)

        # Test exception when qubit out of range
        pytest.raises(NotImplementedError, qc1.add_circuit, qc, start=4)

        qc2 = QubitCircuit(8)
        qc2.add_circuit(qc, start=2)

        # Test if all gates are added
        assert len(qc2.gates) == len(qc.gates)

        # Test if the positions are correct
        for i in range(len(qc2.gates)):
            if qc.gates[i].targets is not None:
                assert (qc2.gates[i].targets[0]
                        == qc.gates[i].targets[0]+2)
            if (isinstance(qc.gates[i], Gate) and
                    qc.gates[i].controls is not None):
                assert (qc2.gates[i].controls[0]
                        == qc.gates[i].controls[0]+2)

        # Test exception when the operators to be added are not gates or measurements
        qc.gates[-1] = 0
        pytest.raises(TypeError, qc2.add_circuit, qc)

    def test_add_state(self):
        """
        Addition of input and output states to a circuit.
        """
        qc = QubitCircuit(3)

        qc.add_state("0", targets=[0])
        qc.add_state("+", targets=[1], state_type="output")
        qc.add_state("-", targets=[1])

        assert qc.input_states[0] == "0"
        assert qc.input_states[2] is None
        assert qc.output_states[1] == "+"

        qc1 = QubitCircuit(10)

        qc1.add_state("0", targets=[2, 3, 5, 6])
        qc1.add_state("+", targets=[1, 4, 9])
        qc1.add_state("A", targets=[1, 4, 9], state_type="output")
        qc1.add_state("A", targets=[1, 4, 9], state_type="output")
        qc1.add_state("beta", targets=[0], state_type="output")
        assert qc1.input_states[0] is None

        assert qc1.input_states[2] == "0"
        assert qc1.input_states[3] == "0"
        assert qc1.input_states[6] == "0"
        assert qc1.input_states[1] == "+"
        assert qc1.input_states[4] == "+"

        assert qc1.output_states[2] is None
        assert qc1.output_states[1] == "A"
        assert qc1.output_states[4] == "A"
        assert qc1.output_states[9] == "A"

        assert qc1.output_states[0] == "beta"

    def test_add_measurement(self):
        """
        Addition of Measurement Object to a circuit.
        """

        qc = QubitCircuit(3, num_cbits=2)

        qc.add_measurement("M0", targets=[0], classical_store=1)
        qc.add_gate("CNOT", targets=[1], controls=[0])
        qc.add_gate("TOFFOLI", controls=[0, 1], targets=[2])
        qc.add_measurement("M1", targets=[2], classical_store=0)
        qc.add_gate("SNOT", targets=[1], classical_controls=[0, 1])
        qc.add_measurement("M2", targets=[1])

        # checking correct addition of measurements
        assert qc.gates[0].targets[0] == 0
        assert qc.gates[0].classical_store == 1
        assert qc.gates[3].name == "M1"
        assert qc.gates[5].classical_store is None

        # checking if gates are added correctly with measurements
        assert qc.gates[2].name == "TOFFOLI"
        assert qc.gates[4].classical_controls == [0, 1]

    @pytest.mark.parametrize('gate', ['X', 'Y', 'Z', 'S', 'T'])
    def test_exceptions(self, gate):
        """
        Text exceptions are thrown correctly for inadequate inputs
        """
        qc = QubitCircuit(2)
        pytest.raises(ValueError, qc.add_gate, gate, targets=[1], controls=[0])

    def test_globalphase_gate_propagators(self):
        qc = QubitCircuit(2)
        qc.add_gate("GLOBALPHASE", arg_value=np.pi / 2)

        [gate] = qc.gates
        assert gate.name == "GLOBALPHASE"
        assert gate.arg_value == np.pi / 2

        [U_expanded] = qc.propagators()
        assert U_expanded == 1j * qp.qeye([2, 2])

        [U_unexpanded] = qc.propagators(expand=False)
        assert U_unexpanded == 1j * qp.qeye([2, 2])

    def test_single_qubit_gates(self):
        """
        Text single qubit gates are added correctly
        """
        qc = QubitCircuit(3)

        qc.add_gate("X", targets=[0])
        qc.add_gate("CY", targets=[1], controls=[0])
        qc.add_gate("Y", targets=[2])
        qc.add_gate("CS", targets=[0], controls=[1])
        qc.add_gate("Z", targets=[1])
        qc.add_gate("CT", targets=[2], controls=[2])
        qc.add_gate("CZ", targets=[0], controls=[0])
        qc.add_gate("S", targets=[1])
        qc.add_gate("T", targets=[2])

        assert qc.gates[8].name == "T"
        assert qc.gates[7].name == "S"
        assert qc.gates[6].name == "CZ"
        assert qc.gates[5].name == "CT"
        assert qc.gates[4].name == "Z"
        assert qc.gates[3].name == "CS"
        assert qc.gates[2].name == "Y"
        assert qc.gates[1].name == "CY"
        assert qc.gates[0].name == "X"

        assert qc.gates[8].targets == [2]
        assert qc.gates[7].targets == [1]
        assert qc.gates[6].targets == [0]
        assert qc.gates[5].targets == [2]
        assert qc.gates[4].targets == [1]
        assert qc.gates[3].targets == [0]
        assert qc.gates[2].targets == [2]
        assert qc.gates[1].targets == [1]
        assert qc.gates[0].targets == [0]

        assert qc.gates[6].controls == [0]
        assert qc.gates[5].controls == [2]
        assert qc.gates[3].controls == [1]
        assert qc.gates[1].controls == [0]

    def test_reverse(self):
        """
        Reverse a quantum circuit
        """
        qc = QubitCircuit(3)

        qc.add_gate("RX", targets=[0], arg_value=3.141,
                    arg_label=r"\pi/2")
        qc.add_gate("CNOT", targets=[1], controls=[0])
        qc.add_measurement("M1", targets=[1])
        qc.add_gate("SNOT", targets=[2])
        # Keep input output same

        qc.add_state("0", targets=[0])
        qc.add_state("+", targets=[1], state_type="output")
        qc.add_state("-", targets=[1])

        qc_rev = qc.reverse_circuit()

        assert qc_rev.gates[0].name == "SNOT"
        assert qc_rev.gates[1].name == "M1"
        assert qc_rev.gates[2].name == "CNOT"
        assert qc_rev.gates[3].name == "RX"

        assert qc_rev.input_states[0] == "0"
        assert qc_rev.input_states[2] is None
        assert qc_rev.output_states[1] == "+"

    def test_user_gate(self):
        """
        User defined gate for QubitCircuit
        """
        def customer_gate1(arg_values):
            mat = np.zeros((4, 4), dtype=np.complex128)
            mat[0, 0] = mat[1, 1] = 1.
            mat[2:4, 2:4] = gates.rx(arg_values).full()
            return Qobj(mat, dims=[[2, 2], [2, 2]])

        def customer_gate2():
            mat = np.array([[1., 0],
                            [0., 1.j]])
            return Qobj(mat, dims=[[2], [2]])

        qc = QubitCircuit(3)
        qc.user_gates = {"CTRLRX": customer_gate1,
                         "T1": customer_gate2}
        qc.add_gate("CTRLRX", targets=[1, 2], arg_value=np.pi/2)
        qc.add_gate("T1", targets=[1])
        props = qc.propagators()
        result1 = tensor(identity(2), customer_gate1(np.pi/2))
        np.testing.assert_allclose(props[0].full(), result1.full())
        result2 = tensor(identity(2), customer_gate2(), identity(2))
        np.testing.assert_allclose(props[1].full(), result2.full())

    def test_N_level_system(self):
        """
        Test for circuit with N-level system.
        """
        mat3 = qp.rand_unitary_haar(3)

        def controlled_mat3(arg_value):
            """
            A qubit control an operator acting on a 3 level system
            """
            control_value = arg_value
            dim = mat3.dims[0][0]
            return (tensor(fock_dm(2, control_value), mat3) +
                    tensor(fock_dm(2, 1 - control_value), identity(dim)))

        qc = QubitCircuit(2, dims=[3, 2])
        qc.user_gates = {"CTRLMAT3": controlled_mat3}
        qc.add_gate("CTRLMAT3", targets=[1, 0], arg_value=1)
        props = qc.propagators()
        final_fid = qp.average_gate_fidelity(mat3, ptrace(props[0], 0) - 1)
        assert pytest.approx(final_fid, 1.0e-6) == 1

        init_state = basis([3, 2], [0, 1])
        result = qc.run(init_state)
        final_fid = qp.fidelity(result, props[0] * init_state)
        assert pytest.approx(final_fid, 1.0e-6) == 1.

    @pytest.mark.repeat(10)
    def test_run_teleportation(self):
        """
        Test circuit run and mid-circuit measurement functionality
        by repeating the teleportation circuit on multiple random kets
        """

        teleportation = _teleportation_circuit()

        state = tensor(rand_ket(2), basis(2, 0), basis(2, 0))
        initial_measurement = Measurement("start", targets=[0])
        _, initial_probabilities = initial_measurement.measurement_comp_basis(state)

        teleportation_sim = CircuitSimulator(teleportation)

        teleportation_sim_results = teleportation_sim.run(state)
        state_final = teleportation_sim_results.get_final_states(0)

        final_measurement = Measurement("start", targets=[2])
        _, final_probabilities = final_measurement.measurement_comp_basis(state_final)

        np.testing.assert_allclose(initial_probabilities, final_probabilities)

    def test_runstatistics_teleportation(self):
        """
        Test circuit run_statistics on teleportation circuit
        """

        teleportation = _teleportation_circuit()
        final_measurement = Measurement("start", targets=[2])
        initial_measurement = Measurement("start", targets=[0])

        original_state = tensor(rand_ket(2), basis(2, 0), basis(2, 0))
        _, initial_probabilities = initial_measurement.measurement_comp_basis(original_state)

        teleportation_results = teleportation.run_statistics(original_state)
        states = teleportation_results.get_final_states()
        probabilities = teleportation_results.get_probabilities()

        for i, state in enumerate(states):
            state_final = state
            prob = probabilities[i]
            _, final_probabilities = final_measurement.measurement_comp_basis(state_final)
            np.testing.assert_allclose(initial_probabilities,
                                       final_probabilities)
            assert prob == pytest.approx(0.25, abs=1e-7)

        mixed_state = sum(p * ket2dm(s) for p, s in zip(probabilities, states))
        dm_state = ket2dm(original_state)

        teleportation2 = _teleportation_circuit2()

        final_state = teleportation2.run(dm_state)
        _, probs1 = final_measurement.measurement_comp_basis(final_state)
        _, probs2 = final_measurement.measurement_comp_basis(mixed_state)

        np.testing.assert_allclose(probs1, probs2)

    def test_measurement_circuit(self):

        qc = _measurement_circuit()
        simulators = _simulators_sv(qc)
        labels = ["00", "01", "10", "11"]

        for label in labels:
            state = bell_state(label)
            for i, simulator in enumerate(simulators):
                simulator.run(state)
                if label[0] == "0":
                    assert simulator.cbits[0] == simulator.cbits[1]
                else:
                    assert simulator.cbits[0] != simulator.cbits[1]

    def test_gate_product(self):

        filename = "qft.qasm"
        filepath = Path(__file__).parent / 'qasm_files' / filename
        qc = read_qasm(filepath)

        U_list_expanded = qc.propagators()
        U_list = qc.propagators(expand=False)

        inds_list = []

        for gate in qc.gates:
            if isinstance(gate, Measurement):
                continue
            else:
                inds_list.append(gate.get_all_qubits())

        U_1, _ = gate_sequence_product(U_list,
                                       inds_list=inds_list,
                                       expand=True)
        U_2 = gate_sequence_product(U_list_expanded, left_to_right=True,
                                    expand=False)

        np.testing.assert_allclose(U_1.full(), U_2.full())

    def test_wstate(self):

        filename = "w-state.qasm"
        filepath = Path(__file__).parent / 'qasm_files' / filename
        qc = read_qasm(filepath)

        rand_state = rand_ket(2)
        state = tensor(tensor(basis(2, 0), basis(2, 0), basis(2, 0)),
                       rand_state)

        fourth = Measurement("test_rand", targets=[3])

        _, probs_initial = fourth.measurement_comp_basis(state)

        simulators = _simulators_sv(qc)

        for simulator in simulators:
            result = simulator.run_statistics(state)
            final_states = result.get_final_states()
            result_cbits = result.get_cbits()

            for i, final_state in enumerate(final_states):
                _, probs_final = fourth.measurement_comp_basis(final_state)
                np.testing.assert_allclose(probs_initial, probs_final)
                assert sum(result_cbits[i]) == 1

    _latex_template = r"""
\documentclass{standalone}
\usepackage[braket]{qcircuit}
\renewcommand{\qswap}{*=<0em>{\times}}
\begin{document}
\Qcircuit @C=1cm @R=1cm {
%s}
\end{document}
"""

    def test_latex_code_teleportation_circuit(self):
        qc = _teleportation_circuit()
        latex = qc.latex_code()
        assert latex == self._latex_template % "\n".join([
            r" & \lstick{c1} &  \qw  &  \qw  &  \qw  &  \qw"
            r"  &  \qw \cwx[4]  &  \qw  &  \qw  &  \ctrl{2}  & \qw \\ ",
            r" & \lstick{c0} &  \qw  &  \qw  &  \qw  &  \qw"
            r"  &  \qw  &  \qw \cwx[2]  &  \ctrl{1}  &  \qw  & \qw \\ ",
            r" & \lstick{\ket{0}} &  \qw  &  \targ  &  \qw  &  \qw"
            r"  &  \qw  &  \qw  &  \gate{X}  &  \gate{Z}  & \qw \\ ",
            r" & \lstick{\ket{0}} &  \gate{{\rm H}}  &  \ctrl{-1}  &"
            r"  \targ  &  \qw  &  \qw  &  \meter &  \qw  &  \qw  & \qw \\ ",
            r" & \lstick{\ket{q0}} &  \qw  &  \qw  &  \ctrl{-1}  &"
            r"  \gate{{\rm H}}  &  \meter &  \qw  &  \qw  &  \qw  & \qw \\ ",
            "",
        ])

    H = Qobj([[1/np.sqrt(2), 1/np.sqrt(2)], [1/np.sqrt(2), -1/np.sqrt(2)]])
    H_zyz_gates = _ZYZ_rotation(H)
    H_zyz_quantum_circuit = QubitCircuit(1)
    H_zyz_quantum_circuit.add_gates(H_zyz_gates)
    sigmax_zyz_gates = _ZYZ_rotation(sigmax())
    sigmax_zyz_quantum_circuit = QubitCircuit(1)
    sigmax_zyz_quantum_circuit.add_gates(sigmax_zyz_gates)

    @pytest.mark.parametrize(
        "valid_input, correct_result",
        [(H_zyz_gates, H), 
        (sigmax_zyz_gates, sigmax())]
        )
    def test_add_gates(self, valid_input, correct_result):
        circuit = QubitCircuit(1)
        circuit.add_gates(valid_input)
        result = gate_sequence_product(circuit.propagators())
        assert(result == correct_result)

    @pytest.mark.parametrize(
        "valid_input, correct_result",
        [(H_zyz_quantum_circuit, H),
        (sigmax_zyz_quantum_circuit, sigmax())]
        )
    def test_compute_unitary(
            self, valid_input, correct_result):
        final_output = valid_input.compute_unitary()
        assert(isinstance(final_output, Qobj))
        assert(final_output == correct_result)

    def test_latex_code(self):
        qc = QubitCircuit(1, num_cbits=1, reverse_states=True)
        qc.add_measurement("M0", targets=0, classical_store=0)
        exp = \
            ' &  &  \\qw \\cwx[1]  & \\qw \\\\ \n &  &  \\meter & \\qw \\\\ \n'
        assert qc.latex_code() == self._latex_template % exp

    def test_latex_code_non_reversed(self):
        qc = QubitCircuit(1, num_cbits=1, reverse_states=False)
        qc.add_measurement("M0", targets=0, classical_store=0)
        exp = ' &  &  \\meter & \\qw \\\\ \n &  ' + \
              '&  \\qw \\cwx[-1]  & \\qw \\\\ \n'
        assert qc.latex_code() == self._latex_template % exp

    @pytest.mark.skipif(
                shutil.which("pdflatex") is None,
                reason="requires pdflatex"
                )
    def test_export_image(self, in_temporary_directory):
        from qutip_qip import circuit
        qc = QubitCircuit(2, reverse_states=False)
        qc.add_gate("CSIGN", controls=[0], targets=[1])

        if "png" in circuit.CONVERTERS:
            file_png200 = "exported_pic_200.png"
            file_png400 = "exported_pic_400.png"
            qc.draw("png", 200, file_png200.split('.')[0], "")
            qc.draw("png", 400.5, file_png400.split('.')[0], "")
            assert file_png200 in os.listdir('.')
            assert file_png400 in os.listdir('.')
            assert os.stat(file_png200).st_size < os.stat(file_png400).st_size
        if "svg" in circuit.CONVERTERS:
            file_svg = "exported_pic.svg"
            qc.draw("svg", file_svg.split('.')[0], "")
            assert file_svg in os.listdir('.')

    def test_deprecation_warning(self):
        # Make them available for backward compatibility.
        with pytest.warns(DeprecationWarning):
            from qutip_qip.circuit import Gate, Measurement
            Gate("X", 0)
